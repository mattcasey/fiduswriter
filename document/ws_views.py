import uuid
import atexit
from copy import deepcopy

from document.helpers.session_user_info import SessionUserInfo
from document.helpers.serializers import PythonWithURLSerializer
from base.ws_handler import BaseWebSocketHandler
import logging
from tornado.escape import json_decode, json_encode
from tornado.websocket import WebSocketClosedError
from document.models import AccessRight, COMMENT_ONLY, CAN_UPDATE_DOCUMENT, \
    CAN_COMMUNICATE, ExportTemplate
from document.views import get_accessrights
from avatar.templatetags.avatar_tags import avatar_url

from style.models import DocumentStyle, CitationStyle, CitationLocale

logger = logging.getLogger(__name__)


class WebSocket(BaseWebSocketHandler):
    sessions = dict()

    def open(self, document_id):
        logger.debug('Websocket opened')
        self.messages = {
            'server': 0,
            'client': 0,
            'last_ten': []
        }
        response = dict()
        current_user = self.get_current_user()
        if current_user is None:
            response['type'] = 'access_denied'
            self.id = 0
            self.send_message(response)
            return
        self.user_info = SessionUserInfo()
        doc_db, can_access = self.user_info.init_access(
            document_id, current_user)
        if can_access:
            if doc_db.id in WebSocket.sessions:
                logger.debug("Serving already opened file")
                self.doc = WebSocket.sessions[doc_db.id]
                self.id = max(self.doc['participants']) + 1
                self.doc['participants'][self.id] = self
                logger.debug("id when opened %s" % self.id)
            else:
                logger.debug("Opening file")
                self.id = 0
                self.doc = {
                    'db': doc_db,
                    'participants': {
                        0: self
                    },
                    'last_diffs': json_decode(doc_db.last_diffs),
                    'comments': json_decode(doc_db.comments),
                    'settings': json_decode(doc_db.settings),
                    'contents': json_decode(doc_db.contents),
                    'metadata': json_decode(doc_db.metadata),
                    'version': doc_db.version,
                    'diff_version': doc_db.diff_version,
                    'comment_version': doc_db.comment_version,
                    'title': doc_db.title,
                    'id': doc_db.id
                }
                WebSocket.sessions[doc_db.id] = self.doc
            response['type'] = 'welcome'
            serializer = PythonWithURLSerializer()
            export_temps = serializer.serialize(
                ExportTemplate.objects.all()
            )
            document_styles = serializer.serialize(
                DocumentStyle.objects.all(),
                use_natural_foreign_keys=True
            )
            cite_styles = serializer.serialize(
                CitationStyle.objects.all()
            )
            cite_locales = serializer.serialize(
                CitationLocale.objects.all()
            )
            response['styles'] = {
                'export_templates': [obj['fields'] for obj in export_temps],
                'document_styles': [obj['fields'] for obj in document_styles],
                'citation_styles': [obj['fields'] for obj in cite_styles],
                'citation_locales': [obj['fields'] for obj in cite_locales],
            }
            self.send_message(response)

    def confirm_diff(self, request_id):
        response = {
            'type': 'confirm_diff',
            'request_id': request_id
        }
        self.send_message(response)

    def send_document(self):
        response = dict()
        response['type'] = 'doc_data'
        doc_owner = self.doc['db'].owner
        response['doc_info'] = {
            'id': self.doc['id'],
            'is_owner': self.user_info.is_owner,
            'access_rights': self.user_info.access_rights,
            'owner': {
                'id': doc_owner.id,
                'name': doc_owner.readable_name,
                'avatar': avatar_url(doc_owner, 80),
                'team_members': []
            }
        }
        if self.doc['diff_version'] < self.doc['version']:
            logger.error('!!!diff version issue!!!')
            self.doc['diff_version'] = self.doc['version']
            self.doc["last_diffs"] = []
        elif self.doc['diff_version'] > self.doc['version']:
            needed_diffs = self.doc['diff_version'] - self.doc['version']
            # We only send those diffs needed by the receiver.
            response['doc_info']['unapplied_diffs'] = self.doc[
                "last_diffs"][-needed_diffs:]
            logger.debug('Adding %d diffs' % needed_diffs)
        else:
            response['doc_info']['unapplied_diffs'] = []
        response['doc'] = {
            'version': self.doc['version'],
            'title': self.doc['title'],
            'contents': self.doc['contents'],
            'metadata': self.doc['metadata'],
            'settings': self.doc['settings']
        }
        if self.user_info.access_rights == 'read-without-comments':
            response['doc']['comments'] = []
        elif self.user_info.access_rights == 'review':
            # Reviewer should only get his/her own comments
            filtered_comments = {}
            for key, value in self.doc["comments"].items():
                if value["user"] == self.user_info.user.id:
                    filtered_comments[key] = value
            response['doc']['comments'] = filtered_comments
        else:
            response['doc']['comments'] = self.doc["comments"]
        response['doc']['comment_version'] = self.doc["comment_version"]
        for team_member in doc_owner.leader.all():
            tm_object = dict()
            tm_object['id'] = team_member.member.id
            tm_object['name'] = team_member.member.readable_name
            tm_object['avatar'] = avatar_url(team_member.member, 80)
            response['doc_info']['owner']['team_members'].append(tm_object)
        collaborators = get_accessrights(
            AccessRight.objects.filter(document__owner=doc_owner)
        )
        response['doc_info']['collaborators'] = collaborators
        if self.user_info.is_owner:
            the_user = self.user_info.user
            response['doc_info']['owner']['email'] = the_user.email
            response['doc_info']['owner']['username'] = the_user.username
            response['doc_info']['owner']['first_name'] = the_user.first_name
            response['doc_info']['owner']['last_name'] = the_user.last_name
        else:
            the_user = self.user_info.user
            response['user'] = dict()
            response['user']['id'] = the_user.id
            response['user']['name'] = the_user.readable_name
            response['user']['avatar'] = avatar_url(the_user, 80)
            response['user']['email'] = the_user.email
            response['user']['username'] = the_user.username
            response['user']['first_name'] = the_user.first_name
            response['user']['last_name'] = the_user.last_name
        response['doc_info']['session_id'] = self.id
        self.send_message(response)

    def on_message(self, message):
        if self.user_info.document_id not in WebSocket.sessions:
            logger.debug('receiving message for closed document')
            return
        parsed = json_decode(message)
        logger.debug("Type %s, server %d, client %d, id %d" % (
            parsed["type"], parsed["s"], parsed["c"], self.id
        ))
        if parsed["type"] == 'request_resend':
            self.resend_messages(parsed["from"])
            return
        if parsed["c"] < (self.messages["client"] + 1):
            # Receive a message already received at least once. Ignore.
            return
        elif parsed["c"] > (self.messages["client"] + 1):
            # Messages from the client have been lost.
            logger.debug('REQUEST RESEND FROM CLIENT')
            self.write_message({
                'type': 'request_resend',
                'from': self.messages["client"]
            })
            return
        elif parsed["s"] < self.messages["server"]:
            # Message was sent either simultaneously with message from server
            # or a message from the server previously sent never arrived.
            # Resend the messages the client missed.
            logger.debug('SIMULTANEOUS')
            self.messages["client"] += 1
            self.resend_messages(parsed["s"])
            if (parsed["type"] == "diff"):
                self.send_message({
                    'type': 'reject_diff',
                    'request_id': parsed['request_id']
                })
            return
        # Message order is correct. We continue processing the data.
        self.messages["client"] += 1

        if parsed["type"] == 'get_document':
            self.send_document()
        elif parsed["type"] == 'participant_update' and self.can_communicate():
            self.handle_participant_update()
        elif parsed["type"] == 'chat' and self.can_communicate():
            self.handle_chat(parsed)
        elif parsed["type"] == 'check_diff_version':
            self.check_diff_version(parsed)
        elif parsed["type"] == 'selection_change':
            self.handle_selection_change(parsed)
        elif (
            parsed["type"] == 'update_doc' and
            self.can_update_document()
        ):
            self.handle_document_update(parsed)
        elif parsed["type"] == 'update_title' and self.can_update_document():
            self.handle_title_update(parsed)
        elif parsed["type"] == 'diff' and self.can_update_document():
            self.handle_diff(parsed)

    def resend_messages(self, from_no):
        to_send = self.messages["server"] - from_no
        logger.debug('resending messages: %d' % to_send)
        logger.debug(
            'Server: %d, from: %d' % (
                self.messages["server"],
                from_no
            )
        )
        if to_send > len(self.messages['last_ten']):
            # Too many messages requested. We have to abort.
            logger.debug('cannot fix it')
            self.send_document()
            return
        for message in self.messages['last_ten'][0-to_send:]:
            message['c'] = self.messages['client']
            logger.debug(message)
            self.write_message(message)

    def update_document(self, changes):
        if changes['version'] == self.doc['version']:
            # Document hasn't changed, return.
            return
        elif (
            changes['version'] > self.doc['diff_version'] or
            changes['version'] < self.doc['version']
        ):
            # The version number is too high. Possibly due to server restart.
            # Do not accept it, and send a document instead.
            self.send_document()
            return
        else:
            # The saved version does not contain all accepted diffs, so we keep
            # the remaining ones + 1000 in case a client needs to reconnect and
            # is missing some.
            remaining_diffs = 1000 + \
                self.doc['diff_version'] - changes['version']
            self.doc['last_diffs'] = self.doc['last_diffs'][-remaining_diffs:]
        self.doc['title'] = changes['title']
        self.doc['contents'] = changes['contents']
        self.doc['metadata'] = changes['metadata']
        self.doc['settings'] = changes['settings']
        self.doc['version'] = changes['version']

    def update_title(self, title):
        self.doc['title'] = title

    def update_comments(self, comments_updates):
        comments_updates = deepcopy(comments_updates)
        for cd in comments_updates:
            id = str(cd["id"])
            if cd["type"] == "create":
                del cd["type"]
                self.doc["comments"][id] = cd
            elif cd["type"] == "delete":
                del self.doc["comments"][id]
            elif cd["type"] == "update":
                self.doc["comments"][id]["comment"] = cd["comment"]
                if "review:isMajor" in cd:
                    self.doc["comments"][id][
                        "review:isMajor"] = cd["review:isMajor"]
            elif cd["type"] == "add_answer":
                comment_id = str(cd["commentId"])
                if "answers" not in self.doc["comments"][comment_id]:
                    self.doc["comments"][comment_id]["answers"] = []
                del cd["type"]
                self.doc["comments"][comment_id]["answers"].append(cd)
            elif cd["type"] == "delete_answer":
                comment_id = str(cd["commentId"])
                for answer in self.doc["comments"][comment_id]["answers"]:
                    if answer["id"] == cd["id"]:
                        self.doc["comments"][comment_id][
                            "answers"].remove(answer)
            elif cd["type"] == "update_answer":
                comment_id = str(cd["commentId"])
                for answer in self.doc["comments"][comment_id]["answers"]:
                    if answer["id"] == cd["id"]:
                        answer["answer"] = cd["answer"]
            self.doc['comment_version'] += 1

    def handle_participant_update(self):
        WebSocket.send_participant_list(self.user_info.document_id)

    def handle_document_update(self, parsed):
        self.update_document(parsed["doc"])
        WebSocket.save_document(self.user_info.document_id, False)
        message = {
            "type": 'check_hash',
            "diff_version": parsed["doc"]["version"],
            "hash": parsed["hash"]
        }
        WebSocket.send_updates(message, self.user_info.document_id, self.id)

    def handle_title_update(self, parsed):
        self.update_title(parsed["title"])
        WebSocket.save_document(self.user_info.document_id, False)

    def handle_chat(self, parsed):
        chat = {
            "id": str(uuid.uuid4()),
            "body": parsed['body'],
            "from": self.user_info.user.id,
            "type": 'chat'
        }
        WebSocket.send_updates(chat, self.user_info.document_id)

    def handle_selection_change(self, parsed):
        if self.user_info.document_id in WebSocket.sessions and parsed[
                "diff_version"] == self.doc['diff_version']:
            WebSocket.send_updates(
                parsed, self.user_info.document_id, self.id)

    # Checks if the diff only contains changes to comments.
    def only_comments(self, parsed_diffs):
        allowed_operations = ['addMark', 'removeMark']
        only_comment = True
        for diff in parsed_diffs:
            if not (diff['stepType'] in allowed_operations and diff[
                    'mark']['type'] == 'comment'):
                only_comment = False
        return only_comment

    def handle_diff(self, parsed):
        pdv = parsed["diff_version"]
        ddv = self.doc['diff_version']
        logger.debug("PDV: %d, DDV: %d" % (pdv, ddv))
        pcv = parsed["comment_version"]
        dcv = self.doc['comment_version']
        if (
            self.user_info.access_rights in COMMENT_ONLY and
            not self.only_comments(parsed['diff'])
        ):
            logger.error(
                (
                    'received non-comment diff from comment-only '
                    'collaborator. Discarding.'
                )
            )
            return
        if pdv == ddv and pcv == dcv:
            self.doc["last_diffs"].extend(parsed["diff"])
            self.doc['diff_version'] += len(parsed["diff"])
            self.update_comments(parsed["comments"])
            self.confirm_diff(parsed["request_id"])
            WebSocket.send_updates(
                parsed,
                self.user_info.document_id,
                self.id,
                self.user_info.user.id
            )
        elif pdv > ddv:
            # Client has a higher version than server. Something is fishy!
            logger.debug('unfixable')
        elif pdv < ddv:
            if pdv + len(self.doc["last_diffs"]) >= ddv:
                # We have enough last_diffs stored to fix it.
                logger.debug("can fix it")
                number_diffs = \
                    parsed["diff_version"] - self.doc['diff_version']
                response = {
                    "type": "diff",
                    "server_fix": True,
                    "diff_version": parsed["diff_version"],
                    "diff": self.doc["last_diffs"][number_diffs:],
                    "reject_request_id": parsed["request_id"],
                }
                self.send_message(response)
            else:
                logger.debug('unfixable')
                # Client has a version that is too old to be fixed
                self.send_document()
        else:
            logger.error('comment_version incorrect!')

    def check_diff_version(self, parsed):
        pdv = parsed["diff_version"]
        ddv = self.doc['diff_version']
        logger.debug("PDV: %d, DDV: %d" % (pdv, ddv))
        if pdv == ddv:
            response = {
                "type": "confirm_diff_version",
                "diff_version": pdv,
            }
            self.send_message(response)
            return
        elif pdv + len(self.doc["last_diffs"]) >= ddv:
            logger.debug("can fix it")
            number_diffs = pdv - ddv
            response = {
                "type": "diff",
                "server_fix": True,
                "diff_version": pdv,
                "diff": self.doc["last_diffs"][number_diffs:],
            }
            logger.debug(response)
            self.send_message(response)
            return
        else:
            logger.debug('unfixable')
            # Client has a version that is too old
            self.send_document()
            return

    def can_update_document(self):
        return self.user_info.access_rights in CAN_UPDATE_DOCUMENT

    def can_communicate(self):
        return self.user_info.access_rights in CAN_COMMUNICATE

    def on_close(self):
        logger.debug('Websocket closing')
        if (
            hasattr(self, 'user_info') and
            hasattr(self.user_info, 'document_id') and
            self.user_info.document_id in WebSocket.sessions and
            hasattr(self, 'id') and
            self.id in WebSocket.sessions[
                self.user_info.document_id
            ]['participants']
        ):
            del self.doc['participants'][self.id]
            if len(self.doc['participants'].keys()) == 0:
                WebSocket.save_document(self.user_info.document_id, True)
                del WebSocket.sessions[self.user_info.document_id]
                logger.debug("noone left")

    def send_message(self, message):
        self.messages['server'] += 1
        message['c'] = self.messages['client']
        message['s'] = self.messages['server']
        self.messages['last_ten'].append(message)
        self.messages['last_ten'] = self.messages['last_ten'][-10:]
        logger.debug("Sending: Type %s, Server: %d, Client: %d, id: %d" % (
            message["type"],
            message['s'],
            message['c'],
            self.id
        ))
        if message["type"] == 'diff':
            logger.debug("Diff version: %d" % message["diff_version"])
        self.write_message(message)

    @classmethod
    def send_participant_list(cls, document_id):
        if document_id in WebSocket.sessions:
            participant_list = []
            for session_id, waiter in cls.sessions[
                document_id
            ]['participants'].items():
                access_rights = waiter.user_info.access_rights
                if access_rights not in CAN_COMMUNICATE:
                    continue
                participant_list.append({
                    'session_id': session_id,
                    'id': waiter.user_info.user.id,
                    'name': waiter.user_info.user.readable_name,
                    'avatar': avatar_url(waiter.user_info.user, 80)
                })
            message = {
                "participant_list": participant_list,
                "type": 'connections'
            }
            WebSocket.send_updates(message, document_id)

    @classmethod
    def send_updates(cls, message, document_id, sender_id=None, user_id=None):
        logger.debug(
            "Sending message to %d waiters",
            len(cls.sessions[document_id])
        )
        for waiter in cls.sessions[document_id]['participants'].values():
            if waiter.id != sender_id:
                access_rights = waiter.user_info.access_rights
                if "comments" in message and len(message["comments"]) > 0:
                    # Filter comments if needed
                    if access_rights == 'read-without-comments':
                        # The reader should not receive the comments update, so
                        # we remove the comments from the copy of the message
                        # sent to the reviewer. We still need to send the rest
                        # of the message as it may contain other diff
                        # information.
                        message = deepcopy(message)
                        message['comments'] = []
                    elif (
                        access_rights == 'review' and
                        user_id != waiter.user_info.user.id
                    ):
                        # The reviewer should not receive comments updates from
                        # others than themselves, so we remove the comments
                        # from the copy of the message sent to the reviewer
                        # that are not from them. We still need to sned the
                        # rest of the message as it may contain other diff
                        # information.
                        message = deepcopy(message)
                        message['comments'] = []
                elif (
                    message['type'] in ["chat", "connections"] and
                    access_rights not in CAN_COMMUNICATE
                ):
                    continue
                elif (
                    message['type'] == "selection_change" and
                    access_rights not in CAN_COMMUNICATE and
                    user_id != waiter.user_info.user.id
                ):
                    continue
                try:
                    waiter.send_message(message)
                except WebSocketClosedError:
                    logger.error("Error sending message", exc_info=True)

    @classmethod
    def save_document(cls, document_id, all_have_left):
        doc = cls.sessions[document_id]
        doc_db = doc['db']
        doc_db.title = doc['title'][-255:]
        doc_db.version = doc['version']
        doc_db.diff_version = doc['diff_version']
        doc_db.comment_version = doc['comment_version']
        doc_db.contents = json_encode(doc['contents'])
        doc_db.metadata = json_encode(doc['metadata'])
        doc_db.settings = json_encode(doc['settings'])
        if all_have_left:
            remaining_diffs = doc['diff_version'] - doc['version']
            if remaining_diffs > 0:
                doc['last_diffs'] = doc['last_diffs'][-remaining_diffs:]
            else:
                doc['last_diffs'] = []
        doc_db.last_diffs = json_encode(doc['last_diffs'])
        doc_db.comments = json_encode(doc['comments'])
        logger.debug('saving document # %d' % doc_db.id)
        logger.debug('version %d' % doc_db.version)
        doc_db.save()

    @classmethod
    def save_all_docs(cls):
        for document_id in cls.sessions:
            cls.save_document(document_id, True)

atexit.register(WebSocket.save_all_docs)
