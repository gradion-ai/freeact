import time

from google import genai


def rerun_on_google_genai_resource_exhausted(wait_time_s: float):
    def _filter(err, name, test, plugin):
        err_class, err_value, _ = err
        match err_class:
            case genai.errors.ClientError:
                time.sleep(wait_time_s)
                return "RESOURCE_EXHAUSTED" in str(err_value)
            case _:
                return False

    return _filter
