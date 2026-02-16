"""
Stream large Firestore collections in batches.
NEVER do db.collection("scanner_logs").get() — that's 76K docs into memory.

Session 28C — Assignment 20.
NEW FILE — does not modify any existing code.
"""

import logging

logger = logging.getLogger("rcb.collection_streamer")


def stream_collection(db, collection_name, batch_size=500, where_clauses=None):
    """
    Yields batches of documents. Memory-safe for any collection size.

    Args:
        db: Firestore client
        collection_name: str
        batch_size: int (default 500)
        where_clauses: list of (field, op, value) tuples

    Yields:
        list of Firestore document snapshots (one batch at a time)

    Usage::

        for batch in stream_collection(db, "scanner_logs", batch_size=200):
            for doc in batch:
                process(doc.to_dict())
    """
    query = db.collection(collection_name)

    if where_clauses:
        for field_path, op, value in where_clauses:
            query = query.where(field_path, op, value)

    query = query.order_by("__name__").limit(batch_size)

    while True:
        docs = list(query.get())

        if not docs:
            break

        yield docs

        last_doc = docs[-1]

        # Rebuild query with start_after for next batch
        query = db.collection(collection_name)
        if where_clauses:
            for field_path, op, value in where_clauses:
                query = query.where(field_path, op, value)
        query = query.order_by("__name__").start_after(last_doc).limit(batch_size)


def count_collection_safe(db, collection_name):
    """
    Count documents without loading them all into memory.

    Falls back to streaming + counting if the aggregation API
    is not available.
    """
    # Try the aggregation API first (Firestore >= 2.16)
    try:
        from google.cloud.firestore_v1.aggregation import AggregationQuery
        agg = AggregationQuery(db.collection(collection_name))
        agg.count(alias="total")
        results = agg.get()
        for result in results:
            for agg_result in result:
                return agg_result.value
    except Exception:
        pass

    # Fallback: stream and count
    count = 0
    for batch in stream_collection(db, collection_name, batch_size=1000):
        count += len(batch)
    return count
