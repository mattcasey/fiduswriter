import {obj2Node} from "./json"
import {createSlug, findImages} from "./tools"
import {zipFileCreator} from "./zip"
import {BibliographyDB} from "../bibliography/bibliographyDB"

/** The current Fidus Writer filetype version.
 * The importer will not import from a different version and the exporter
  * will include this number in all exports.
 */
let FW_FILETYPE_VERSION = "1.2"

/** Create a Fidus Writer document and upload it to the server as a backup.
 * @function uploadNative
 * @param aDocument The document to turn into a Fidus Writer document and upload.
 */
export let uploadNative = function(editor) {
    let doc = editor.doc
    exportNative(doc, ImageDB, BibDB, function(doc, shrunkImageDB, shrunkBibDB, images) {
        exportNativeFile(editor.doc, shrunkImageDB, shrunkBibDB, images, true, editor)
    })
}

export let downloadNative = function(aDocument, bibDB, imageDB) {
    if (bibDB && imageDB) {
        exportNative(aDocument, imageDB, bibDB, exportNativeFile)
    } else if (bibDB) {
        usermediaHelpers.getAnImageDB(aDocument.owner, function(imageDB) {
            exportNative(aDocument, imageDB, bibDB,
                exportNativeFile)
        })
    } else if (imageDB) {
        let bibGetter = new BibliographyDB(aDocument.owner, false, false, false)
        bibGetter.getBibDB(function(bibDB, bibCats) {
            exportNative(aDocument,
                imageDB,
                bibDB, exportNativeFile)
        })
    } else {
        let bibGetter = new BibliographyDB(aDocument.owner, false, false, false)
        bibGetter.getBibDB(function(bibDB, bibCats) {
            usermediaHelpers.getAnImageDB(function(imageDB) {
                exportNative(aDocument, imageDB,
                bibDB, exportNativeFile)
            })
        })
    }

}

// used in copy
export let exportNative = function(aDocument, anImageDB, aBibDB, callback) {
    let shrunkBibDB = {},
        citeList = []

    $.addAlert('info', gettext('File export has been initiated.'))

    let contents = obj2Node(aDocument.contents)

    let images = findImages(contents)

    let imageUrls = _.pluck(images, 'url')


    let shrunkImageDB = _.filter(anImageDB, function(image) {
        return (imageUrls.indexOf(image.image.split('?').shift()) !== -
            1)
    })

    jQuery(contents).find('.citation').each(function() {
        citeList.push(jQuery(this).attr('data-bib-entry'))
    })

    citeList = _.uniq(citeList.join(',').split(','))

    if (citeList.length === 1 && citeList[0] === '') {
        citeList = []
    }

    for (let i in citeList) {
        shrunkBibDB[citeList[i]] = aBibDB[citeList[i]]
    }

    callback(aDocument, shrunkImageDB, shrunkBibDB, images)

}

let exportNativeFile = function(aDocument, shrunkImageDB,
    shrunkBibDB,
    images, upload, editor) {

    if ('undefined' === typeof upload) {
        upload = false
    }

    let httpOutputList = images

    let outputList = [{
        filename: 'document.json',
        contents: JSON.stringify(aDocument),
    }, {
        filename: 'images.json',
        contents: JSON.stringify(shrunkImageDB)
    }, {
        filename: 'bibliography.json',
        contents: JSON.stringify(shrunkBibDB)
    }, {
        filename: 'filetype-version',
        contents: FW_FILETYPE_VERSION
    }]

    zipFileCreator(outputList, httpOutputList, createSlug(
            aDocument.title) +
        '.fidus', 'application/fidus+zip', false, upload, editor)
}
