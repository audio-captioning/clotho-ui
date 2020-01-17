#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import os
from typing import MutableMapping, Dict, List, NewType, Any, Union

import botocore
from tqdm import tqdm

from tools import *

__author__ = 'Samuel Lipping -- Tampere University'
__docformat__ = 'reStructuredText'
__all__ = ['Task', 'layout_params_from_file',
           'list_all_qualification_types',
           'create_custom_qualifications',
           'list_qualifications_for_hit']

# For easier type hinting
MTurkClient = NewType('MTurkClient', botocore.client.BaseClient)
DataDict = NewType('DataDict', MutableMapping[str, Any])
ResultDict = NewType('ResultDict', MutableMapping[str, List[str]])


class Task:

    def __init__(self,
                 config: MutableMapping[str, Any]):
        task_config = config['TASKS'][
            config['CURRENT']['task']
        ]

        if 'collapse_instructions_token' in task_config:
            self.collapse_token = task_config['collapse_instructions_token']
        else:
            self.collapse_token = None

        self.title = task_config['Title']
        self.title += f'(Batch {config["CURRENT"]["batch"]})'

        self.desc = task_config['Description']
        self.keywords = task_config['Keywords']
        self.layout = task_config['SBX_LAYOUT_ID'] if config['USE_SANDBOX'] else task_config['PROD_LAYOUT_ID']
        self.reward = task_config['Reward']
        self.max_assigns = task_config['MaxAssignments']
        self.ut_id = config['UNIQUE_IDS'][
            config['CURRENT']['batch']
        ]


def layout_params_from_file(ifile: str,
                            delim: str = ',',
                            constants: MutableMapping[str, str] = {}) \
        -> List[Dict[str, str]]:
    """ Create generator for layout parameters read from csv file

    :param ifile: Input file path
    :type ifile: str
    :param delim: Input file delimiter
    :type delim: str
    :param constants: Constant layout parameters to add.
    :type constants: dict[str, str]
    :return: Layout parameters, format for one HIT (row):
    {
        'Name': <layout_param_name>,
        'Value': <layout_param_value>
    }
    :rtype: list[dict[str, str]]
    """
    with open(ifile, "r") as f:
        reader = csv.reader(f, delimiter=delim, quotechar='"')
        titles = next(reader)

        # Sometimes an additional row of Column 1, 2.. is added automatically when editing csv
        if any(t.startswith('Column') for t in titles):
            titles = next(reader)

        for row in reader:
            values = row
            layout_params = []
            for i in constants:
                layout_params.append({'Name': i, 'Value': constants[i]})

            for i, value in enumerate(values):
                layout_params.append({'Name': titles[i], 'Value': value})

            yield layout_params


def list_all_qualification_types(client: MTurkClient) \
        -> List[DataDict]:
    """ List all the qualification types associated with given AMT client

    :param client: AMT client
    :type client: botocore.client.BaseClient
    :return: List of qualification type dicts
    :rtype: list[dict[str, any]]
    """
    results = []

    q = client.list_qualification_types(
        MaxResults=100,
        MustBeRequestable=False,
        MustBeOwnedByCaller=True
    )

    while q["NumResults"] > 0:
        nt = q["NextToken"]
        results.extend(q["QualificationTypes"])

        q = client.list_qualification_types(
            MaxResults=100,
            MustBeRequestable=False,
            MustBeOwnedByCaller=True,
            NextToken=nt
        )

    return results


def create_custom_qualifications(client: MTurkClient) \
        -> Dict[str, Union[str, List[str]]]:
    """ Checks existence of and creates custom qualifications (blacklist and batch qualifications)

    :param client: AMT client
    :type client: botocore.client.BaseClient
    :return: Custom qualification IDs
    :rtype: dict[str, any]
    """
    custom_qualifications = {
        'BLACKLIST': '',
        'BATCH': []
    }

    q_types = list_all_qualification_types(client)

    q_names = [qt['Name'] for qt in q_types]

    for rnd in range(1, 11):
        name = f'Participated in experiment Batch {rnd}'
        desc = 'Workers with this qualification have already participated in ' \
               'this batch and will not be able to ' \
               'participate in this batch anymore.'

        if name not in q_names:
            resp = client.create_qualification_type(
                Name=name,
                Description=desc,
                Keywords='audio,Tampere University of Technology',
                QualificationTypeStatus='Active',
                AutoGranted=True,
                AutoGrantedValue=1,
                RetryDelayInSeconds=0
            )
            qid = resp['QualificationType']['QualificationTypeId']
        else:
            qid = [qt['QualificationTypeId'] for qt in q_types if qt['Name'] == name][0]

        custom_qualifications['BATCH'].append(qid)

    blacklist_name = 'Experimental settings'
    if blacklist_name not in q_names:
        resp = client.create_qualification_type(
            Name=blacklist_name,
            Description=blacklist_name,
            QualificationTypeStatus='Active',
            AutoGranted=False
        )
        qid = resp['QualificationType']['QualificationTypeId']
    else:
        qid = [qt['QualificationTypeId'] for qt in q_types if qt['Name'] == blacklist_name][0]

    custom_qualifications['BLACKLIST'] = qid

    return custom_qualifications


def list_qualifications_for_hit(config: MutableMapping[str, Any],
                                custom_qualifications: MutableMapping[str, Union[str, List[str]]]) \
        -> List[Dict[str, Any]]:
    """ Create a list of the needed qualifications for the HIT

    :param config: HIT settings
    :type config: dict
    :param custom_qualifications: Custom qualifications
    :type custom_qualifications: dict[str, any]
    :return: List of needed qualifications for HIT
    :rtype: list[dict[atr, any]]
    """
    task_config = config['TASKS'][
        config['CURRENT']['task']
    ]

    # If task has specific defined requirements, use those instead of global ones
    if 'REQUIREMENTS' in task_config:
        approval_rating, approved_hits, locations = \
            tuple(
                [task_config['REQUIREMENTS'][q_name] for q_name in {'APPROVAL_RATE', 'APPROVED_HITS', 'LOCATION'}]
            )
    else:
        approval_rating, approved_hits, locations = \
            tuple(
                [config['REQUIREMENTS'][q_name] for q_name in ['APPROVAL_RATE', 'APPROVED_HITS', 'LOCATION']]
            )

    qualifications = [{
        # Location qualification
        'ActionsGuarded': 'Accept',
        'Comparator': 'In',
        'LocaleValues': [{'Country': c} for c in locations],
        'QualificationTypeId': '00000000000000000071',
        "RequiredToPreview": False
    }, {
        # Approval rating qualification
        'ActionsGuarded': 'Accept',
        'Comparator': 'GreaterThan',
        'IntegerValues': [approval_rating],
        'QualificationTypeId': '000000000000000000L0',
        'RequiredToPreview': False
    }, {
        # Approved HITs qualification
        'ActionsGuarded': 'Accept',
        'Comparator': 'GreaterThan',
        'IntegerValues': [approved_hits],
        'QualificationTypeId': '00000000000000000040',
        'RequiredToPreview': False
    }]

    # Blacklist and batch qualifications not needed for sandbox testing
    if not config['USE_SANDBOX']:
        # Add blacklist qualification
        qualifications.append({
            'ActionsGuarded': 'DiscoverPreviewAndAccept',
            'Comparator': 'DoesNotExist',
            'QualificationTypeId': custom_qualifications['BLACKLIST'],
            'RequiredToPreview': False
        })
        # Add batch qualification
        qualifications.append({
            'ActionsGuarded': 'Accept',
            'Comparator': 'DoesNotExist',
            'QualificationTypeId': custom_qualifications['BATCH'][
                config['CURRENT']['batch'] - 1
            ],
            'RequiredToPreview': False
        })

    return qualifications


def main():
    config = read_yaml('config.yaml')
    aws_keys = read_yaml('aws_keys.yaml')

    req_annotation = get_req_annotation_for_batch(config)

    client = get_client(aws_keys, config)

    task = Task(config)

    if not config['USE_SANDBOX'] or config['USE_REQ_WITH_SANDBOX']:
        inc_flag = 0
        if os.path.exists('custom_qualifications.yaml'):
            custom_qualifications = read_yaml('custom_qualifications.yaml')

            if any([i not in custom_qualifications for i in ['BLACKLIST', 'BATCH']]):
                inc_flag = 1
            elif len(custom_qualifications['BLACKLIST']) < 1:
                inc_flag = 1
            elif len(custom_qualifications['BATCH']) < 10:
                inc_flag = 1
        else:
            inc_flag = 1

        if inc_flag == 1:
            custom_qualifications = create_custom_qualifications(client)

            write_yaml(custom_qualifications, 'custom_qualifications.yaml')

        qualifications = list_qualifications_for_hit(config, custom_qualifications)
    else:
        qualifications = []

    N = len([1 for _ in open(config['CURRENT']['input_data_file'])]) - 1
    constants = {'unique_id': task.ut_id}

    if task.collapse_token is not None:
        constants['collapse_token'] = task.collapse_token

    for layout_params in tqdm(
            layout_params_from_file(
                config['CURRENT']['input_data_file'],
                constants=constants
            ),
            total=N
    ):
        # audioType is the same for all, so it can be added automatically if not in the file.
        contains_type = 0
        try:
            for i, params in enumerate(layout_params):
                if params['Name'] == 'audioType':
                    contains_type = 1
                elif params['Name'] in ['DescriptionText', 'EditedCaption', 'captions']:
                    layout_params[i] = {
                        'Name': params['Name'],
                        # AMT requires ASCII-only
                        'Value': replace_non_ascii(params['Value']).replace('"', "'")
                    }
        except:
            pass
        if contains_type == 0:
            layout_params.append({'Name': 'audioType', 'Value': 'audio/wav'})

        resp = client.create_hit(
            LifetimeInSeconds=14 * 24 * 3600,
            AssignmentDurationInSeconds=20 * 60,
            MaxAssignments=task.max_assigns,
            Reward=task.reward,
            Title=task.title,
            Description=task.desc,
            Keywords=task.keywords,
            HITLayoutId=task.layout,
            HITLayoutParameters=layout_params,
            QualificationRequirements=qualifications,
            RequesterAnnotation=req_annotation
        )

    print(
        f'Published {N} HITs with:'
        f'\n\tTitle: {task.title}'
        f'\n\tHIT Group Id: {resp["HIT"]["HITGroupId"]}'
    )


if __name__ == '__main__':
    main()

# EOF
