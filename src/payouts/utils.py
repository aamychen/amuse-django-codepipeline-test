def get_hw_exception_code(exception):
    '''
    Extract error_code from HyperwalletAPIException and HyperwalletException

    :param exception:
    :return: code
    '''
    error_code = "EXCEPTION_PARSER_ERROR"
    try:
        message = exception.message
        error = message.get("errors")[0]
        error_code = error.get("code")
        return error_code
    except:
        return error_code
