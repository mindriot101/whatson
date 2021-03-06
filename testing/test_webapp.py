# pylint: disable=missing-module-docstring,missing-function-docstring
import pytest
from whatson.webapp import create_app, interpolate_months
import datetime
from unittest import mock


@pytest.fixture(scope="module")
def client(connection):
    app = create_app(connection)
    with app.test_client() as client:
        yield client


def test_getting_months(client, cursor):
    today = datetime.date.today()
    start_date = datetime.date(today.year + 1, 1, 2)
    end_date = datetime.date(today.year + 1, 2, 3)
    cursor.execute(
        """INSERT INTO shows (theatre, title, image_url, link_url, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s)""",
        ("test", "show", "", "", start_date, end_date),
    )

    rv = client.get("/api/months")
    data = rv.get_json()

    expected = [
        {"year": today.year + 1, "month": 1},
        {"year": today.year + 1, "month": 2},
    ]
    assert data["dates"] == expected


def test_only_getting_valid_months(client, cursor):
    today = datetime.date.today()

    # Insert a show well into the past
    start_date = datetime.date(today.year - 2, today.month, today.day)
    end_date = datetime.date(today.year - 2, today.month + 2, 1)
    cursor.execute(
        """INSERT INTO shows (theatre, title, image_url, link_url, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s)""",
        ("test", "show1", "", "", start_date, end_date),
    )

    # Now add a show in the future
    start_date = datetime.date(today.year + 1, 1, 2)
    end_date = datetime.date(today.year + 1, 2, 3)
    cursor.execute(
        """INSERT INTO shows (theatre, title, image_url, link_url, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s)""",
        ("test", "show2", "", "", start_date, end_date),
    )

    rv = client.get("/api/months")
    data = rv.get_json()

    assert {"year": today.year - 2, "month": today.month} not in data["dates"]
    assert {"year": today.year + 1, "month": 1} in data["dates"]


def test_something():
    start = {"year": 2019, "month": 11}
    end = {"year": 2020, "month": 8}

    dates = list(interpolate_months([start, end]))

    assert dates == [
        {"year": 2019, "month": 11},
        {"year": 2019, "month": 12},
        {"year": 2020, "month": 1},
        {"year": 2020, "month": 2},
        {"year": 2020, "month": 3},
        {"year": 2020, "month": 4},
        {"year": 2020, "month": 5},
        {"year": 2020, "month": 6},
        {"year": 2020, "month": 7},
        {"year": 2020, "month": 8},
    ]
