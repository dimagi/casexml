/*
 * Filter that only returns cases.  Used by the change listener.
 */
function(doc, req)
{
    var doc_type = doc.doc_type;
    switch (doc_type) {
        case "CommCareCase":
        case "CommCareCase-Deleted":
            return true;
        default:
            return false;
    }
}
