from rest_framework.renderers import JSONRenderer


class CustomJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        # If data already has the expected structure, return it as-is
        if isinstance(data, dict) and "errors" in data and "data" in data:
            return super().render(data, accepted_media_type, renderer_context)

        response_data = {"errors": {}, "data": {}}

        if renderer_context:
            response = renderer_context["response"]
            if response.status_code < 300:
                if response.status_code == 204:
                    response_data["data"] = None
                else:
                    response_data["data"] = data
            else:
                response_data["errors"] = data if data else {}
        else:
            response_data["data"] = data

        return super().render(response_data, accepted_media_type, renderer_context)
