function (doc) {
    if (doc.doc_type === 'CommCareCase') {
        var external_id = doc.external_id,
            phone_number = doc.contact_phone_number;
        if (external_id) {
            emit(["external_id", doc.domain, external_id], null);
        }
        if (phone_number) {
            emit(["phone_number", doc.domain, phone_number], null);
        }
    }
}
