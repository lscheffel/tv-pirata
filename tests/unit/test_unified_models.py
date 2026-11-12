"""Unit tests for canonical unified domain models."""

from src.backend.models.unified import TorrentRelease, UnifiedEpisode, UnifiedSeason, UnifiedShow


def test_clean_html_strips_tags():
    raw_html = "<p>This is a <b>great</b> show with <a href='#'>links</a>.</p>"
    clean = UnifiedShow.clean_html(raw_html)
    assert clean == "This is a great show with links."


def test_torrent_release_parsing_eztv():
    eztv_item = {
        "id": 999,
        "hash": "abc123hash",
        "filename": "Breaking.Bad.S05E16.1080p.BluRay.x264.mkv",
        "title": "Breaking Bad S05E16 1080p BluRay",
        "season": "5",
        "episode": "16",
        "magnet_url": "magnet:?xt=urn:btih:abc123hash",
        "seeds": "350",
        "peers": "45",
        "size_bytes": "2147483648",
    }

    release = TorrentRelease.from_eztv(eztv_item)
    assert release.id == 999
    assert release.hash == "abc123hash"
    assert release.season == 5
    assert release.episode == 16
    assert release.quality == "1080p"
    assert release.seeds == 350
    assert release.peers == 45
    assert release.size_bytes == 2147483648


def test_unified_show_defaults():
    show = UnifiedShow(
        id=101,
        title="Dandadan",
        overview="Occult comedy action series.",
        genres=["Animation", "Comedy", "Sci-Fi"],
        rating=8.7,
        seasons=[
            UnifiedSeason(
                id=1,
                season_number=1,
                name="Season 1",
                episode_count=12,
                episodes=[
                    UnifiedEpisode(
                        id=1,
                        episode_number=1,
                        season_number=1,
                        title="That's How Love Starts, Ya Know!",
                    )
                ],
            )
        ],
    )

    assert show.id == 101
    assert show.source_provider == "tmdb"
    assert show.seasons[0].episode_count == 12
    assert len(show.seasons[0].episodes) == 1
    assert show.seasons[0].episodes[0].episode_number == 1
