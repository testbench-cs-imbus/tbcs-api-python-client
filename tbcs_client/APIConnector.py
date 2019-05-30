import requests
import json
import os
import urllib3

from typing import List

""" Class for connecting to a TestBench CS REST-API

The APIConnector class wraps a set of API-calls against the TestBench CS REST-API, that can be used to
create test_cases within TestBench CS, start test executions and report test results. This class expects
a JSON-configuration file with name 'tbcs.config.json' to be placed inside your project root.

When provided with valid configuration, you can simply call any of this classes get-, create- and
report-functions from any instance of this class. Redundant steps such as authenticating with the API
are handled internally.
"""


class APIConnector:
    test_step_status_undefined: str = 'Undefined'
    test_step_status_passed: str = 'Passed'
    test_step_status_failed: str = 'Failed'
    test_status_calculated: str = 'Calculated'
    test_status_failed: str = 'Failed'
    test_status_inprogress: str = 'InProgress'
    test_status_passed: str = 'Passed'

    __base_url: str
    __headers: dict
    __tenant_name: str
    __tenant_id: int = -1
    __username: str
    __password: str
    __user_id: int = -1
    __product_id: str
    __session: requests.sessions

    def __init__(self):
        with open('../tbcs.config.json') as config_file:
            config_data: dict = json.load(config_file)
            self.__base_url = f'https://{config_data["server_address"]}'
            self.__tenant_name = config_data['tenant_name']
            self.__product_id = config_data['product_id']
            self.__username = config_data['tenant_user']
            self.__password = config_data['password']
            if not config_data['use_system_proxy']:
                os.environ['no_proxy'] = '*'
                os.environ['NO_PROXY'] = '*'

            self.__session = requests.Session()
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # TODO
            self.__session.verify = False  # TODO
            self.__log_in()

    def create_test_case(
            self,
            test_case_name: str,
            external_id: str,
            test_steps: List[str]
    ) -> str:
        response_create: requests.Response = self.__send_request(
            http_method=self.__session.post,
            endpoint=f'/api/tenants/{self.__tenant_id}/products/{self.__product_id}/specifications/testCases',
            expected_status_code=201,
            data=json.dumps({'name': test_case_name})
        )

        test_case_id: str = str(json.loads(response_create.text)['testCaseId'])

        test_case_data: dict = {
            'name': test_case_name,
            'description': {'text': test_case_name},
            'responsibles': [self.__user_id],
            'customFields': [],
            'isAutomated': True,
            'toBeReviewed': False,
            'externalId': {'value': external_id}
        }

        self.__send_request(
            http_method=self.__session.patch,
            endpoint=f'/api/tenants/{self.__tenant_id}/products/{self.__product_id}/specifications/testCases/{test_case_id}',
            expected_status_code=200,
            data=json.dumps(test_case_data)
        )

        for test_step in test_steps:
            test_step_data: dict = {
                'testStepBlock': 'Test',
                'description': test_step
            }

            self.__send_request(
                http_method=self.__session.post,
                endpoint=f'/api/tenants/{self.__tenant_id}/products/{self.__product_id}/specifications/testCases/{test_case_id}/testSteps',
                expected_status_code=201,
                data=json.dumps(test_step_data)
            )

        return test_case_id

    def get_test_case_by_external_id(
            self,
            external_id: str
    ) -> dict:
        return {}  # TODO

    def get_test_case_by_id(
            self,
            test_case_id: str
    ) -> dict:
        response: requests.Response = self.__send_request(
            http_method=self.__session.get,
            endpoint=f'/api/tenants/{self.__tenant_id}/products/{self.__product_id}/specifications/testCases/{test_case_id}',
            expected_status_code=200
        )

        return json.loads(response.text)

    def start_execution(
            self,
            test_case_id: str
    ) -> str:
        response: requests.Response = self.__send_request(
            http_method=self.__session.post,
            endpoint=f'/api/tenants/{self.__tenant_id}/products/{self.__product_id}/executions/testCases/{test_case_id}',
            expected_status_code=201
        )

        return str(json.loads(response.text)['executionId'])

    def get_execution_by_external_id(
            self,
            external_id
    ) -> dict:
        return {}  # TODO

    def get_execution_by_id(
            self,
            test_case_id: str,
            execution_id: str
    ) -> dict:
        response: requests.Response = self.__send_request(
            http_method=self.__session.get,
            endpoint=f'/api/tenants/{self.__tenant_id}/products/{self.__product_id}/executions/testCases/{test_case_id}/executions/{execution_id}',
            expected_status_code=200
        )

        return json.loads(response.text)

    def report_step_result(
            self,
            test_case_id,
            execution_id,
            test_step_id,
            result
    ):
        self.__send_request(
            http_method=self.__session.put,
            endpoint=f'/api/tenants/{self.__tenant_id}/products/{self.__product_id}/executions/testCases/{test_case_id}/executions/{execution_id}/testSteps/{test_step_id}/result',
            expected_status_code=200,
            data=f'"{result}"'
        )

    def report_test_case_result(
            self,
            test_case_id,
            execution_id,
            result
    ):
        result_data: dict = {
            'executionStatus': result
        }
        self.__send_request(
            http_method=self.__session.patch,
            endpoint=f'/api/tenants/{self.__tenant_id}/products/{self.__product_id}/executions/testCases/{test_case_id}/executions/{execution_id}',
            expected_status_code=200,
            data=json.dumps(result_data)
        )

    def __send_request(
            self,
            http_method: requests.api,
            endpoint: str,
            expected_status_code: int,
            data: str = ''
    ) -> requests.Response:
        response: requests.Response = http_method(
            url=f'{self.__base_url}{endpoint}',
            data=data,
            headers=self.__headers
        )

        if response.status_code == 401:
            if endpoint == '/api/tenants/login/session':
                raise Exception('Unable to authenticate', response)
            else:
                self.__log_in()
                return self.__send_request(http_method, endpoint, expected_status_code, data)
        elif response.status_code == expected_status_code:
            return response
        else:
            # TODO: Error handling (e.g. headers and data)
            raise Exception(f'{endpoint} failed', response.text)

    def __log_in(self):
        self.__headers: dict = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Charset': 'UTF-8'
        }
        auth_data: dict = {
            'force': True,
            'tenantName': self.__tenant_name,
            'login': self.__username,
            'password': self.__password
        }
        response: requests.Response = self.__send_request(
            http_method=self.__session.post,
            endpoint='/api/tenants/login/session',
            expected_status_code=201,
            data=json.dumps(auth_data)
        )
        response_data: dict = json.loads(response.text)
        self.__headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Charset': 'UTF-8',
            'Authorization': f'Bearer {response_data["sessionToken"]}'
        }
        self.__tenant_id = response_data['tenantId']
        self.__user_id = response_data['userId']
