from dataclasses import dataclass, fields, asdict
from datetime import datetime, timezone
from flask import Request, make_response, Response
import functions_framework
from google.cloud import datastore
import sys
from threading import Lock
from traceback import format_exception
from typing import cast, Mapping, Any
from werkzeug.exceptions import BadRequest

# store database instance in global variable
# to avoid re-initializing
db = None
LOCK = Lock()


@functions_framework.http
def db_call(request: Request) -> Response:
    try:
        return dispatch_call(request)
    except Exception:
        headers = {"Access-Control-Allow-Origin": "*"}
        status = 500
        traceback_lines = format_exception(*sys.exc_info())
        err_detail = {"error": "".join(traceback_lines)}
        return make_response(err_detail, status, headers)


def dispatch_call(request: Request) -> Response:
    """
    Dispatch call to appropriate database operation.

    Example to store vote = {
        "function": "vote",
        "args": {
            "voted_for": "Vote_compact",
            "layout_seen": "C_first",
            "screen_dims": "1680 x 1050"
        }
    }

    Example to retrieve count = {
        "function": "count"
    }

    Example to retrieve recent votes = {
        "function": "list"
    }
    """
    if request.method == "OPTIONS":
        # respond to CORS preflight requests
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        cors_status = 204
        return make_response("", cors_status, cors_headers)

    common_headers = {"Access-Control-Allow-Origin": "*"}
    status_code = 200
    if not request.is_json:
        raise BadRequest("MIME type must be application/json")
    json = request.get_json()
    # cast needed for type hints
    json = cast(Mapping, json)
    if json["function"] == "vote":
        answer = store_vote(json)
    elif json["function"] == "count":
        answer = get_count()
    elif json["function"] == "list":
        answer = {"error_msg": "not implemented"}
        status_code = 400
    else:
        answer = {"error_msg": f"bad request: {json}"}
        status_code = 400
    response = make_response(answer)
    response.status_code = status_code
    response.headers.extend(common_headers)
    return response


def store_vote(json: Mapping) -> Any:
    """
    Store a vote.
    """
    global db
    if db is None:
        with LOCK:
            if db is None:
                db = DataModel()
    args = json["args"]
    vote_data = NewVote(
        args["voted_for"],
        args["layout_seen"],
        args["screen_dims"]
    )
    return asdict(db.submit_vote(vote_data))


def get_count() -> Any:
    """
    Retreive the count of votes.
    """
    global db
    if db is None:
        with LOCK:
            if db is None:
                db = DataModel()
    return asdict(db.get_count())


@dataclass(frozen=True)
class NewVote:
    """
    Data to input when casting a new vote.
    This is basically the same as Vote, but without the unique id
    and timestamp which will be assigned by the DataModel.

    Parameters:
    voted_for - either "Vote_compact" or "Vote_long"
    layout_seen - "C_first" if compact was shown first or "L_first"
                  if long was shown first
    screen_dims - string of form "width x height"
    """
    voted_for: str
    layout_seen: str
    screen_dims: str
    VCOMPACT = "Vote_compact"
    VLONG = "Vote_long"
    VALID_VOTES = [VCOMPACT, VLONG]
    VALID_LAYOUTS = ["C_first", "L_first"]

    def validate(self) -> None:
        assert self.voted_for in NewVote.VALID_VOTES
        assert self.layout_seen in NewVote.VALID_LAYOUTS


@dataclass(frozen=True, slots=True)
class Vote:
    """
    Immutable voting data including unique id and timestamp.
    """
    key: tuple[str, int]
    layout_seen: str
    screen_dims: str
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class CountVotes:
    """
    Immutable count of total votes
    """
    count_vote_compact: int
    count_vote_long: int
    COMPACT = "count_vote_compact"
    LONG = "count_vote_long"


class DataModel:
    """
    Datamodel that connects to google-cloud-datastore database
    """
    PROJECT = "mp-indents-01"
    TOTAL_KEY = ("Votes", "totals")

    def __init__(self) -> None:
        self.client = datastore.Client(project=DataModel.PROJECT)
        self.totals_key = self.client.key(*DataModel.TOTAL_KEY)

    def create_initial_count(self) -> str:
        """
        Create initial count of zero. Do not call this in production.
        """
        totals = datastore.Entity(self.totals_key)
        for f in fields(CountVotes):
            totals[f.name] = 0
        self.client.put(totals, timeout=5)
        return str(totals)

    def submit_vote(self, vote: NewVote) -> Vote:
        """
        Submit a vote and store in the database.
        Returns the vote info together with its unique id and timestamp.
        """
        # prepare data outside transaction for performance
        vote.validate()
        data = asdict(vote)
        del data["voted_for"]
        partial_key = self.client.key(vote.voted_for, parent=self.totals_key)
        record = datastore.Entity(partial_key)
        record.update(data)
        timestamp = datetime.now(timezone.utc)
        record["timestamp"] = timestamp

        # store totals separately
        if vote.voted_for == vote.VCOMPACT:
            name = CountVotes.COMPACT
        elif vote.voted_for == vote.VLONG:
            name = CountVotes.LONG
        else:
            raise ValueError(f"invalid voted_for: {vote.voted_for}")

        with self.client.transaction():
            totals = self.client.get(self.totals_key)
            totals[name] += 1
            # need a transaction, not enough to use put_multi()
            self.client.put_multi([record, totals], timeout=5)

        # unique id not generated by database until after transaction closed
        return Vote(
            (record.key.kind, record.key.id),
            **record
        )

    def get_count(self) -> CountVotes:
        """
        Return count of the votes
        """
        totals = self.client.get(self.totals_key)
        return CountVotes(
            count_vote_compact=totals[CountVotes.COMPACT],
            count_vote_long=totals[CountVotes.LONG]
        )
