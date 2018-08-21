def lock_record(record, related=None):
    model = type(record)
    qs = model._default_manager.select_for_update().filter(pk=record.pk)
    if related:
        qs = qs.select_related(*related)
    return qs.first()
