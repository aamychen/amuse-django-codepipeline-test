def preprocessing_filter_spec(endpoints):
    """Only generate API docs for analytics for now"""

    for path, path_regex, method, callback in endpoints:
        if path.startswith("/api/analytics"):
            yield path, path_regex, method, callback
