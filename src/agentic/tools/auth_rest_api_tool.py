from typing import Callable, Optional

from .rest_tool_v2 import RESTAPIToolV2

class AuthorizedRESTAPITool(RESTAPIToolV2):
    def get_tools(self) -> list[Callable]:
        return [
            self.add_request_header,
            self.get_resource,
            self.post_resource,
            self.put_resource,
            self.patch_resource,
            self.delete_resource,
            self.debug_request,
        ]

    def test_credential(self, cred, secrets: dict) -> str|None:
        """ Test that the given credential secrets are valid. Return None if OK, otherwise
            return an error message.
        """
        msgs = []
        if secrets.get("bearer_token"):
            valid, msg = self.run_context.validate_secret(secrets.get("bearer_token"))
            if not valid:
                msgs.append(msg)
        elif secrets.get("basic_username"):
            valid, msg = self.run_context.validate_secret(secrets.get("basic_username"))
            if not valid:
                msgs.append(msg)
            valid, msg = self.run_context.validate_secret(secrets.get("basic_password"))
            if not valid:
                msgs.append(msg)
        elif secrets.get("request_arg_name"):
            valid, msg = self.run_context.validate_secret(secrets.get("request_arg_value"))
            if not valid:
                msgs.append(msg)
        elif secrets.get("header_name"):
            valid, msg = self.run_context.validate_secret(secrets.get("header_value"))
            if not valid:
                msgs.append(msg)
        return "\n".join(msgs) if len(msgs) > 0 else None


    async def get_auth_variable(self):
        auth_type = "none"
        token: str|None = None
        token_name: str = ""
        if self.credentials.get("bearer_token"):
            auth_type = "bearer"
            token=self.credentials.get("bearer_token")
            token_name=self.credentials.get("bearer_token_name") or "Bearer"
        elif self.credentials.get("basic_username"):
            auth_type = "basic"
        elif self.credentials.get("request_arg_name"):
            auth_type = "parameter"
            token = self.credentials.get("request_arg_value")
            token_name = self.credentials.get("request_arg_name") or "api_key"
        
        auth_var = await super().prepare_auth_config(
            auth_type=auth_type,
            username=self.credentials.get("basic_username"), 
            password=self.credentials.get("basic_username"), 
            token=token,
            token_name=token_name,
        )

        if self.credentials.get("header_name"):
            super().add_request_header(
                auth_var, 
                self.credentials.get("header_name"), 
                self.credentials.get("header_value")
            )

        return auth_var

    async def get_resource(
            self, 
            url: str, 
            params: dict = {},
        ):
        """ Invoke the GET REST endpoint on the indicated URL, using authentication already configured.
            returns: the JSON response, or the response text and status code.
        """
        return await super().get_resource(url, params, auth_config_var=await self.get_auth_variable())

    async def post_resource(
            self, 
            url: str, 
            content_type: str = "application/json",
            data: str = "{}",
        ):
        """ Invoke the POST REST endpoint, using authentication already configured. 
            Supply a data dictionary of params (as json data). The data will be submitted
            as json or as form data (application/x-www-form-urlencoded).
            Returns the response and status code. 
        """
        return await super().post_resource(url, content_type, data, auth_config_var=await self.get_auth_variable())

    async def put_resource(
            self, 
            url: str, 
            data: str = "{}",
        ):
        """ Invoke the PUT REST endpoint. 
            Supply a data dictionary of params (as json data). 
        """
        return await super().put_resource(url, data, auth_config_var=await self.get_auth_variable())

    async def patch_resource(
            self, 
            url: str, 
            data: str = "{}",
        ):
        """ Invoke the PATCH REST endpoint.
            Supply a data dictionary of params (as json data). 
        """
        return await super().patch_resource(url, data, auth_config_var=await self.get_auth_variable())


    async def delete_resource(
            self, 
            url: str,
    ):
        """ Invoke the DELETE REST endpoint. """
        return await super().delete_resource(url, auth_config_var=await self.get_auth_variable())
