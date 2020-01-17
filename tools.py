#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import MutableMapping, NewType, Any, Dict

import yaml
import boto3
import botocore

__author__ = 'Samuel Lipping -- Tampere University'
__docformat__ = 'reStructuredText'
__all__ = ['get_client',
           'read_yaml',
           'write_yaml',
           'get_req_annotation_for_batch',
           'replace_non_ascii']

# For easier type hinting
MTurkClient = NewType('MTurkClient', botocore.client.BaseClient)


def get_client(keys: MutableMapping[str, str],
               config: MutableMapping[str, Any]) \
        -> MTurkClient:
    """ Create an AMT client object

    :param keys: AWS API keys
    :type keys: dict[str, str]
    :param config: Script settings
    :type config: dict
    :return: The created client object
    :rtype: botocore.client.BaseClient
    """
    if config['USE_SANDBOX']:
        endpoint_url = 'https://mturk-requester-sandbox.us-east-1.amazonaws.com'
    else:
        endpoint_url = 'https://mturk-requester.us-east-1.amazonaws.com'

    return boto3.client(
        'mturk',
        endpoint_url=endpoint_url,
        region_name=config['REGION_NAME'],
        aws_access_key_id=keys['access_key_id'],
        aws_secret_access_key=keys['secret_access_key'],
        config=botocore.config.Config(
            retries=dict(
                max_attempts=10
            )
        )
    )


def read_yaml(ifile: str) \
        -> Dict[str, Any]:
    """ Read a yaml file into a dictionary

    :param ifile: Input file name
    :type ifile: str
    :return: Yaml file contents
    :rtype: dict
    """
    return yaml.load(open(str(ifile)))


def write_yaml(data: MutableMapping[str, Any],
               file: str) \
        -> None:
    """ Write dictionary into a yaml file

    :param data: Data to write
    :type data: dict
    :param file: Output file path
    :type file: str
    """
    yaml.dump(data, open(file, "w"))


def get_req_annotation_for_batch(config: MutableMapping[str, Any]) \
        -> str:
    """ Get the requester annotation for the current batch for the current task

    Format:
        <task_name> Batch <batch_number>

    :param config: Script settings
    :type config: dict
    :return: Requester annotation
    :rtype: str
    """
    return f'{config["CURRENT"]["task"]} Batch {config["CURRENT"]["batch"]}'


def replace_non_ascii(string: str) \
        -> str:
    """ Replace some non-ASCII characters with ASCII characters.
    Used for input sanitation for HIT creation requests.

    :param string: "Unsanitised" string
    :type string: str
    :return: "Sanitised" string
    :rtype: str
    """
    return str(string.replace(u'\xe7', 'c')
               .replace(u'\u2019', "'")
               .replace(u'\xb7', '-')
               .replace(u'\xed', 'i')
               .replace(u'\u201c', "'")
               .replace(u'\u201d', "'")
               .replace(u'\xe0', 'a')
               .replace(u'\xe2', "'"))

# EOF
