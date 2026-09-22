from app.ticker import TickerExtractor


def tickers(result):
    return [match.ticker for match in result.matches]


def test_plain_ticker(session, config):
    assert tickers(TickerExtractor(session, config).extract("I bought NVDA today")) == ["NVDA"]


def test_cashtag(session, config):
    assert tickers(TickerExtractor(session, config).extract("$PLTR calls")) == ["PLTR"]


def test_company_aliases(session, config):
    result = TickerExtractor(session, config).extract("Nvidia and Palantir look strong")
    assert tickers(result) == ["NVDA", "PLTR"]


def test_false_positive(session, config):
    assert tickers(TickerExtractor(session, config).extract("AI is amazing")) == []


def test_blacklisted_symbol_requires_cashtag_even_with_stock_context(session, config):
    config.blacklist.add("NVDA")
    extractor = TickerExtractor(session, config)
    assert tickers(extractor.extract("NVDA stock is amazing")) == []
    assert tickers(extractor.extract("$NVDA stock is amazing")) == ["NVDA"]


def test_unknown_uppercase_is_ignored(session, config):
    assert tickers(TickerExtractor(session, config).extract("THIS IS FINE")) == []


def test_repeated_ticker_matches_are_visible_to_dedup_layer(session, config):
    assert tickers(TickerExtractor(session, config).extract("NVDA then NVDA")) == ["NVDA", "NVDA"]
