import {Plugin, PluginKey} from "prosemirror-state"
import {Decoration, DecorationSet} from "prosemirror-view"
import {sendableSteps} from "prosemirror-collab"

const collabCaretsKey = new PluginKey('collabCarets')

export let getSelectionUpdate = function(state) {
     let {caretUpdate} = collabCaretsKey.getState(state)
     console.log(['getting sel update', caretUpdate])
     return caretUpdate
}

export let updateCollaboratorSelection = function(state, collaborator, data) {
    let {
        decos,
        caretPositions
    } = collabCaretsKey.getState(state)

    let oldCarPos = caretPositions.find(carPos => carPos.sessionId === data.session_id)

    if (oldCarPos) {
        caretPositions = caretPositions.filter(carPos => carPos !== oldCarPos)
        let removeDecos = [oldCarPos.widgetDeco]
        if (oldCarPos.inlineDeco) {
            removeDecos.push(oldCarPos.inlineDeco)
        }
        decos = decos.remove(removeDecos)
    }

    let widgetDom = document.createElement('div')
    let className = `user-${collaborator.colorId}`
    widgetDom.classList.add('caret')
    widgetDom.classList.add(className)
    widgetDom.innerHTML = '<div class="caret-head"></div>'
    widgetDom.firstChild.classList.add(className)
    let tooltip = collaborator.name
    widgetDom.title = tooltip
    widgetDom.firstChild.title = tooltip
    let widgetDeco = Decoration.widget(data.head, widgetDom)
    let newCarPos = {
        sessionId: data.session_id,
        userId: collaborator.id,
        widgetDeco,
        anchor: data.anchor,
        head: data.head
    }
    let addDecos = [widgetDeco]

    if (data.anchor !== data.head) {
        let from = data.head > data.anchor ? data.anchor : data.head
        let to = data.anchor > data.head ? data.anchor : data.head
        let inlineDeco = Decoration.inline(from, to, {
            class: `user-bg-${collaborator.colorId}`
        })
        newCarPos.inlineDeco = inlineDeco
        addDecos.push(inlineDeco)
    }
    caretPositions.push(newCarPos)
    console.log(['addDecos', addDecos, newCarPos])
    decos = decos.add(state.doc, addDecos)

    let transaction = state.tr.setMeta(collabCaretsKey, {
        decos,
        caretPositions,
        caretUpdate: false
    })
    console.log(decos)
    console.log(['getMeta',transaction.getMeta(collabCaretsKey)])
    return transaction
}

export let removeCollaboratorSelection = function(state, data) {
    let {
        decos,
        caretPositions
    } = collabCaretsKey.getState(state)

    let caretPosition = caretPositions.find(carPos => carPos.sessionId === data.session_id)

    if (caretPosition) {
        caretPositions = caretPositions.filter(carPos => carPos !== caretPosition)
        let removeDecos = [caretPosition.widgetDeco]
        if (caretPosition.inlineDeco) {
            removeDecos.push(caretPosition.inlineDeco)
        }
        decos = decos.remove(removeDecos)
        let transaction = state.tr.setMeta(collabCaretsKey, {
            decos,
            caretPositions,
            caretUpdate: false
        })
        return transaction
    }
    return false
}

export let collabCaretsPlugin = function(options) {
    return new Plugin({
        key: collabCaretsKey,
        state: {
            init() {
                return {
                    caretPositions: [],
                    decos: DecorationSet.empty,
                    caretUpdate: false
                }
            },
            apply(tr, prev, oldState, state) {
                let meta = tr.getMeta(collabCaretsKey)
                console.log(['META',meta])
                if (meta) {
                    // There has been an update, return values from meta instead
                    // of previous values
                    return meta
                }
                console.log("NOT MEAT")
                let {
                    decos,
                    caretPositions
                } = this.getState(oldState),
                caretUpdate = false

                decos = decos.map(tr.mapping, tr.doc, {onRemove: deco => {
                    caretPositions = caretPositions.filter(
                        carPos => carPos.widgetDeco !== deco && carPos.inlineDeco !== deco
                    )
                }})


                if (tr.selectionSet && !sendableSteps(state)) {
                    caretUpdate = {anchor: tr.selection.anchor, head: tr.selection.head}
                    console.log(['setting selection', tr])
                }

                return {
                    decos,
                    caretPositions,
                    caretUpdate
                }
            }
        },
        props: {
            decorations(state) {
				let {
					decos
				} = this.getState(state)
                console.log(['sel decos', decos])
				return decos
			}
        }
    })
}
