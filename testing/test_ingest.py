from whatson import ingest
from unittest import mock
import datetime


@mock.patch("whatson.ingest._fetch_html_requests")
def test_albany(client):
    with open("testing/responses/albany.html") as infile:
        client.return_value = infile.read()

    fetcher = ingest.AlbanyFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 29
    assert shows[0]["start_date"] == datetime.date(2020, 1, 1)
    assert shows[-1]["title"] == "The Mersey Beatles 2020"


@mock.patch("whatson.ingest._fetch_html_requests")
def test_belgrade(client):
    with open("testing/responses/belgrade.html") as infile:
        client.return_value = infile.read()

    fetcher = ingest.BelgradeFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 66
    assert shows[0]["start_date"] == datetime.date(2019, 11, 27)
    assert shows[0]["end_date"] == datetime.date(2020, 1, 11)
    assert shows[0]["title"] == "Puss In Boots"

    assert shows[-1]["start_date"] == datetime.date(2020, 11, 25)
    assert shows[-1]["end_date"] == datetime.date(2021, 1, 9)
    assert shows[-1]["title"] == "Beauty and the Beast"


@mock.patch("whatson.ingest._fetch_html_requests")
def test_symphony_hall(client):
    with open("testing/responses/symphony_hall_1.html") as infile:
        resp1 = infile.read()

    with open("testing/responses/symphony_hall_2.html") as infile:
        resp2 = infile.read()

    client.side_effect = [resp1, resp2]

    fetcher = ingest.SymphonyHallFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 24
    assert shows[0]["start_date"] == datetime.date(2020, 1, 5)
    assert shows[0]["end_date"] == datetime.date(2020, 1, 12)
    assert shows[0]["title"] == "We're Going On A Bear Hunt"

    assert shows[-1]["start_date"] == datetime.date(2020, 1, 28)
    assert shows[-1]["end_date"] == datetime.date(2020, 1, 28)
    assert shows[-1]["title"] == "Echo Eternal Youth Arts Festival 2020: Horizons"


@mock.patch("whatson.ingest._fetch_html_requests")
def test_hippodrome(client):
    with open("testing/responses/hippodrome_1.html") as infile:
        resp1 = infile.read()

    with open("testing/responses/hippodrome_2.html") as infile:
        resp2 = infile.read()

    client.side_effect = [resp1, resp2]

    fetcher = ingest.HippodromeFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 32
    assert shows[0]["start_date"] == datetime.date(2020, 1, 5)
    assert shows[0]["end_date"] == datetime.date(2020, 2, 2)
    assert shows[0]["title"] == "Snow White & the Seven Dwarfs"

    assert shows[-1]["start_date"] == datetime.date(2020, 3, 27)
    assert shows[-1]["end_date"] == datetime.date(2020, 3, 28)
    assert shows[-1]["title"] == "DX - Mariposa"


@mock.patch("whatson.ingest._fetch_html_selenium")
def test_resortsworld(client):
    with open("testing/responses/resortsworld.html") as infile:
        client.return_value = infile.read()

    fetcher = ingest.ResortsWorldFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 28
    assert shows[0]["start_date"] == datetime.date(2020, 1, 31)
    assert shows[0]["end_date"] == datetime.date(2020, 2, 1)
    assert shows[0]["title"] == "The Arenacross Tour 2020"
    assert (
        shows[0]["image_url"]
        == "https://d1t1vb5tk5g2b3.cloudfront.net/media/1655/arenacross-2020-arenas.jpg?anchor=center&mode=crop&width=537&height=294&rnd=132185532740000000&quality=60"
    )

    assert shows[-1]["start_date"] == datetime.date(2020, 11, 21)
    assert shows[-1]["end_date"] == datetime.date(2020, 11, 21)
    assert shows[-1]["title"] == "Free Radio Hits Live 2020"


@mock.patch("whatson.ingest._fetch_html_selenium")
def test_arena_bham(client):
    with open("testing/responses/arena_birmingham.html") as infile:
        client.return_value = infile.read()

    fetcher = ingest.ArenaBirminghamFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 61
    assert shows[0]["start_date"] == datetime.date(2020, 1, 16)
    assert shows[0]["end_date"] == datetime.date(2020, 1, 19)
    assert shows[0]["title"] == "Strictly Come Dancing The Live Tour 2020"
    assert (
        shows[0]["image_url"]
        == "https://d38sswc4c2k2dz.cloudfront.net/media/1815/scd-lineup-arenas.jpg?anchor=center&mode=crop&width=537&height=294&rnd=132197819540000000&quality=60"
    )

    assert shows[-1]["start_date"] == datetime.date(2020, 12, 11)
    assert shows[-1]["end_date"] == datetime.date(2020, 12, 11)
    assert shows[-1]["title"] == "Il Divo"


@mock.patch("whatson.ingest._fetch_html_requests")
def test_artrix(client):
    with open("testing/responses/artrix_1.html") as infile:
        resp1 = infile.read()

    with open("testing/responses/artrix_2.html") as infile:
        resp2 = infile.read()

    with open("testing/responses/artrix_3.html") as infile:
        resp3 = infile.read()

    client.side_effect = [resp1, resp2, resp3]

    fetcher = ingest.ArtrixFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 32
    assert shows[0]["start_date"] == datetime.date(2019, 11, 5)
    assert shows[0]["end_date"] == datetime.date(2020, 1, 5)
    assert shows[0]["title"] == "KATHLEEN WATSON AND LYNNE SAWYER  - INSPIRE BY NATURE"

    assert shows[-1]["start_date"] == datetime.date(2020, 1, 18)
    assert shows[-1]["end_date"] == datetime.date(2020, 1, 18)
    assert shows[-1]["title"] == "Polar Squad"


@mock.patch("whatson.ingest._fetch_html_requests")
def test_alex(client):
    with open("testing/responses/alex.html") as infile:
        client.return_value = infile.read()

    fetcher = ingest.AlexFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 63
    assert shows[0]["start_date"] == datetime.date(2020, 1, 8)
    assert shows[0]["end_date"] == datetime.date(2020, 1, 11)
    assert shows[0]["title"] == "Ghost Stories"

    assert shows[-1]["start_date"] == datetime.date(2020, 12, 8)
    assert shows[-1]["end_date"] == datetime.date(2021, 1, 2)
    assert shows[-1]["title"] == "Dreamgirls"


@mock.patch("whatson.ingest._fetch_html_requests")
def test_arts_centre(client):
    with open("testing/responses/arts_centre_1.html") as infile:
        resp1 = infile.read()

    with open("testing/responses/arts_centre_2.html") as infile:
        resp2 = infile.read()

    with open("testing/responses/arts_centre_3.html") as infile:
        resp3 = infile.read()

    client.side_effect = [resp1, resp2, resp3]

    fetcher = ingest.WarwickArtsCentreFetcher()
    shows = list(fetcher.fetch())

    assert len(shows) == 20
    assert shows[0]["start_date"] == datetime.date(2020, 1, 9)
    assert shows[0]["end_date"] == datetime.date(2020, 1, 12)
    assert shows[0]["title"] == "Cinderella"

    assert shows[-1]["start_date"] == datetime.date(2020, 1, 26)
    assert shows[-1]["end_date"] == datetime.date(2020, 1, 26)
    assert (
        shows[-1]["title"]
        == "Warwick Masterclass 2020: Getting Creative with your Fancy Camera"
    )
