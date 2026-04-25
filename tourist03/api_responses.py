from tourist03.dto.common import ErrorResponseDTO, ValidationErrorResponseDTO


ERROR_RESPONSE_REGISTRY = {
    400: {"model": ErrorResponseDTO, "description": "Некорректный запрос"},
    401: {"model": ErrorResponseDTO, "description": "Не авторизован"},
    403: {"model": ErrorResponseDTO, "description": "Нет доступа"},
    404: {"model": ErrorResponseDTO, "description": "Ресурс не найден"},
    409: {"model": ErrorResponseDTO, "description": "Конфликт данных"},
    429: {"model": ErrorResponseDTO, "description": "Слишком много запросов"},
    422: {"model": ValidationErrorResponseDTO, "description": "Ошибка валидации запроса"},
    500: {"model": ErrorResponseDTO, "description": "Внутренняя ошибка сервера"},
}


def error_responses(*status_codes: int):
    return {code: ERROR_RESPONSE_REGISTRY[code] for code in status_codes}
