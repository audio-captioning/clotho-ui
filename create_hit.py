#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import os
import re
from pathlib import Path
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
        self.reward = task_config['Reward']
        self.max_assigns = task_config['MaxAssignments']
        self.ut_id = config['UNIQUE_IDS'][
            config['CURRENT']['batch'] - 1
        ]


def layout_params_from_file(ifile: str,
                            delim: str = ',',
                            constants: MutableMapping[str, str] = {},
                            ignore: set = set()) \
        -> List[Dict[str, str]]:
    """ Create generator for layout parameters read from csv file

    :param ifile: Input file path
    :type ifile: str
    :param delim: Input file delimiter
    :type delim: str
    :param constants: Constant layout parameters to add.
    :type constants: dict[str, str]
    :param ignore: Fields to ignore
    :type ignore: set[str]
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
            param_dict = {}
            for k, v in constants.items():
                param_dict[k] = v

            for i, value in enumerate(values):
                field_name = titles[i]
                if field_name != 'file_name' and field_name not in ignore:
                    param_dict[field_name] = value

            for k, v in param_dict.items():
                layout_params.append({'Name': k, 'Value': v})

            yield layout_params, param_dict


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
        name = f'Participated in annotation Batch {rnd}'
        desc = 'Workers with this qualification have already participated in ' \
               'this batch and will not be able to ' \
               'participate in this batch anymore.'

        if name not in q_names:
            resp = client.create_qualification_type(
                Name=name,
                Description=desc,
                Keywords='audio,Tampere University of Technology,listening',
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
                [task_config['REQUIREMENTS'][q_name] for q_name in ['APPROVAL_RATE', 'APPROVED_HITS', 'LOCATION']]
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


def input_layout_params_into_html(html: str,
                                  layout_params: List[Dict[str, str]],
                                  verbose: bool = False) \
        -> str:
    """ Replaces layout parameter placeholders in html with values.

    Placeholders are of the form ${variable_name}. If unexpected
    parameters are given or an expected parameter is not given,
    a message will be printed to the console, but no exception
    will be raised, since the layout still works with placeholders
    in place of actual values.

    :param verbose: Determines if the function should print out information
    :type verbose: bool
    :param html: The HTML in which to replace placeholders
    :type html: str
    :param layout_params: Layout parameters to place in placeholders
    :type layout_params: list[dict[str,str]]
    :return: The HTML with the placeholders replaces
    :rtype: str
    """
    # See if all the expected parameters are given in layout_params
    expected_params = set(
        [the_param[2:-1] for the_param in re.findall(r"\${[a-zA-Z_1-9]+\}", html)]
    )
    given_params = set([the_param['Name'] for the_param in layout_params])
    for param in expected_params:
        if param not in given_params:
            # if verbose:
            print(f'Expected layout parameter {param} not given.')

    # Replace the placeholders
    new_html = html
    for param in layout_params:
        to_replace = '${' + param['Name'] + '}'
        if to_replace not in new_html:
            if verbose:
                print(f'Unexpected layout parameter: {param["Name"]}.')

        new_html = new_html.replace(
            '${' + param["Name"] + '}',
            param['Value']
        )

    return new_html


def wrap_layout_into_question(html: str,
                              mturk_form_action: str,
                              config: Dict[str, Union[str, int]]) \
        -> str:
    """ Wrap an HTML layout into an HTMLQuestion

    :param config: Layout settings, including template file paths and frame height
    :type config: dict[str, str | int]
    :param mturk_form_action: What URL to use for the form action on mturk.
                            Depends on whether or not sandbox is in use.
    :type mturk_form_action: str
    :param html: HTML to wrap
    :type html: str
    :return: The wrapped HTML
    :rtype: str
    """
    html_template = open(config['HTML_wrapper'], 'r').read()
    xml_template = open(config['question_wrapper'], 'r').read()

    html_content = html_template.format(
        mturk_form_action=mturk_form_action,
        hit_layout=html
    )
    xml = xml_template.format(
        html_content=html_content,
        frame_height=str(config['frame_height'])
    )

    return xml


def main():
    config = read_yaml('config.yaml')
    aws_keys = read_yaml('aws_keys.yaml')

    req_annotation = get_req_annotation_for_batch(config)[0]

    client = get_client(aws_keys, config)

    task = Task(config)

    if not config['USE_SANDBOX']:
        cont = input('You are about to publish production HITs (not sandbox). Continue?')
        if cont.startswith('n'):
            return
    else:
        print(f'Publishing sandbox HITs from {config["CURRENT"]["input_data_file"]}')

    if config['USE_SANDBOX']:
        mturk_form_action = 'https://workersandbox.mturk.com/mturk/externalSubmit'
    else:
        mturk_form_action = 'https://www.mturk.com/mturk/externalSubmit'

    if not config['USE_SANDBOX'] or config['USE_REQ_WITH_SANDBOX']:
        inc_flag = 0
        if os.path.exists('custom_qualifications.yaml'):
            custom_qualifications = read_yaml('custom_qualifications.yaml')

            if custom_qualifications is None:
                inc_flag = 1
            elif any([i not in custom_qualifications for i in ['BLACKLIST', 'BATCH']]):
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

    layout_file = Path(
        config['TASKS'][config['CURRENT']['task']]['LAYOUT_FILE']
    )
    with layout_file.open('r') as f:
        layout_html = f.read()

    for layout_params, param_dict in tqdm(
            layout_params_from_file(
                config['CURRENT']['input_data_file'],
                constants=constants
            ),
            total=N
    ):

        contains_type = 0
        try:
            for i, params in enumerate(layout_params):
                # audioType is the same for all, so it can be added automatically if not in the file.
                if params['Name'] == 'audioType':
                    contains_type = 1
                # Replace non-ASCII
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

        for i in layout_params:
            if i['Name'] in ['file_name', 'audioUrl']:
                assert i['Value'].endswith('.wav')

        question_html = input_layout_params_into_html(
            layout_html,
            layout_params
        )
        question = wrap_layout_into_question(
            question_html,
            mturk_form_action,
            config['LAYOUT']
        )

        hit_kwargs = {
            'LifetimeInSeconds': 14 * 24 * 3600,
            'AssignmentDurationInSeconds': 20 * 60,
            'Reward': task.reward,
            'Title': task.title,
            'Description': task.desc,
            'Keywords': task.keywords,
            'Question': question,
            'QualificationRequirements': qualifications,
            'RequesterAnnotation': req_annotation
        }

        if 'MaxAssignments' in param_dict:
            hit_kwargs['MaxAssignments'] = int(param_dict['MaxAssignments'])
        elif 'SubmissionsReceived' in param_dict:
            ma = task.max_assigns - int(param_dict['SubmissionsReceived'])
            if ma < 0:
                print(f'Error with HIT parameters: Cannot publish less than 0 assignments!')
                ma = 0
            hit_kwargs['MaxAssignments'] = ma
        else:
            hit_kwargs['MaxAssignments'] = task.max_assigns

        resp = client.create_hit(**hit_kwargs)

    print(
        f'Published {N} HITs with:'
        f'\n\tTitle: {task.title}'
        f'\n\tHIT Group Id: {resp["HIT"]["HITGroupId"]}'
    )


if __name__ == '__main__':
    main()

# EOF
