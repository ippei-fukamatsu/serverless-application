import os
from tests_util import TestsUtil
from unittest import TestCase
from me_articles_fraud_create import MeArticlesFraudCreate
from unittest.mock import patch, MagicMock
from boto3.dynamodb.conditions import Key


class TestMeArticlesFraudCreate(TestCase):
    dynamodb = TestsUtil.get_dynamodb_client()

    @classmethod
    def setUpClass(cls):
        TestsUtil.set_all_tables_name_to_env()
        TestsUtil.delete_all_tables(cls.dynamodb)

        # create article_fraud_user_table
        cls.article_fraud_user_table_items = [
            {
                'article_id': 'testid000000',
                'user_id': 'test01',
                'created_at': 1520150272
            },
            {
                'article_id': 'testid000001',
                'user_id': 'test01',
                'created_at': 1520150273
            },
            {
                'article_id': 'testid000002',
                'user_id': 'test02',
                'created_at': 1520150273
            }
        ]
        TestsUtil.create_table(
            cls.dynamodb,
            os.environ['ARTICLE_FRAUD_USER_TABLE_NAME'],
            cls.article_fraud_user_table_items
        )

        # create article_info_table
        article_info_table_items = [
            {
                'article_id': 'testid000000',
                'status': 'public',
                'sort_key': 1520150272000000
            },
            {
                'article_id': 'testid000001',
                'status': 'public',
                'sort_key': 1520150272000001
            },
            {
                'article_id': 'testid000002',
                'status': 'draft',
                'sort_key': 1520150272000002
            }
        ]
        TestsUtil.create_table(
            cls.dynamodb,
            os.environ['ARTICLE_INFO_TABLE_NAME'],
            article_info_table_items
        )

    @classmethod
    def tearDownClass(cls):
        TestsUtil.delete_all_tables(cls.dynamodb)

    def assert_bad_request(self, params):
        test_function = MeArticlesFraudCreate(params, {}, self.dynamodb)
        response = test_function.main()

        self.assertEqual(response['statusCode'], 400)

    @patch('time.time', MagicMock(return_value=1520150272000003))
    def test_main_ok_exist_article_id(self):
        params = {
            'pathParameters': {
                'article_id': self.article_fraud_user_table_items[0]['article_id']
            },
            'requestContext': {
                'authorizer': {
                    'claims': {
                        'cognito:username': 'test03'
                    }
                }
            }
        }

        article_fraud_user_table = self.dynamodb.Table(os.environ['ARTICLE_FRAUD_USER_TABLE_NAME'])
        article_fraud_user_before = article_fraud_user_table.scan()['Items']

        article_fraud_user = MeArticlesFraudCreate(event=params, context={}, dynamodb=self.dynamodb)
        response = article_fraud_user.main()

        article_fraud_user_after = article_fraud_user_table.scan()['Items']

        target_article_id = params['pathParameters']['article_id']
        target_user_id = params['requestContext']['authorizer']['claims']['cognito:username']

        article_fraud_user = self.get_article_fraud_user(target_article_id, target_user_id)

        expected_items = {
            'article_id': target_article_id,
            'user_id': target_user_id,
            'created_at': 1520150272000003
        }

        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(len(article_fraud_user_after), len(article_fraud_user_before) + 1)
        article_fraud_user_param_names = ['article_id', 'user_id', 'created_at']
        for key in article_fraud_user_param_names:
            self.assertEqual(expected_items[key], article_fraud_user[key])

    def test_call_validate_article_existence(self):
        params = {
            'pathParameters': {
                'article_id': 'testid000002'
            },
            'requestContext': {
                'authorizer': {
                    'claims': {
                        'cognito:username': 'test04'
                    }
                }
            }
        }

        mock_lib = MagicMock()
        with patch('me_articles_fraud_create.DBUtil', mock_lib):
            MeArticlesFraudCreate(event=params, context={}, dynamodb=self.dynamodb).main()
            args, kwargs = mock_lib.validate_article_existence.call_args

            self.assertTrue(mock_lib.validate_article_existence.called)
            self.assertTrue(args[0])
            self.assertTrue(args[1])
            self.assertEqual(kwargs['status'], 'public')

    def test_main_ng_exist_user_id(self):
        params = {
            'pathParameters': {
                'article_id': self.article_fraud_user_table_items[0]['article_id']
            },
            'requestContext': {
                'authorizer': {
                    'claims': {
                        'cognito:username': self.article_fraud_user_table_items[0]['user_id']
                    }
                }
            }
        }

        response = MeArticlesFraudCreate(event=params, context={}, dynamodb=self.dynamodb).main()

        self.assertEqual(response['statusCode'], 400)

    def test_validation_with_no_params(self):
        params = {}

        self.assert_bad_request(params)

    def test_validation_article_id_max(self):
        params = {
            'queryStringParameters': {
                'article_id': 'A' * 13
            }
        }

        self.assert_bad_request(params)

    def test_validation_article_id_min(self):
        params = {
            'queryStringParameters': {
                'article_id': 'A' * 11
            }
        }

        self.assert_bad_request(params)

    def get_article_fraud_user(self, article_id, user_id):
        query_params = {
            'KeyConditionExpression': Key('article_id').eq(article_id) & Key('user_id').eq(user_id)
        }
        article_fraud_user_table = self.dynamodb.Table(os.environ['ARTICLE_FRAUD_USER_TABLE_NAME'])
        return article_fraud_user_table.query(**query_params)['Items'][0]
