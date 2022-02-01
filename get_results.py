#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
from pathlib import Path
from typing import MutableMapping, List, Union, NewType, Any, Tuple, Dict

import xmltodict
import botocore

from tools import get_client, get_req_annotation_for_batch, read_yaml, replace_non_ascii

__author__ = 'Samuel Lipping -- Tampere University'
__docformat__ = 'reStructuredText'
__all__ = ['test_hit', 'get_answer_data',
           'write_ans_data_file',
           'get_all_hits',
           'get_hit_assignments',
           'get_all_assignments']

# For easier type hinting
MTurkClient = NewType('MTurkClient', botocore.client.BaseClient)
DataDict = NewType('DataDict', MutableMapping[str, Any])
ResultDict = NewType('ResultDict', MutableMapping[str, List[str]])


def test_hit(hit: DataDict,
             params: MutableMapping[str, List[Any]]) \
        -> bool:
    """ Test HIT (or assignment) for given parameters
    E.g. test_hit(hit, {'HITId': ['123']}) returns True, if the HITId of the HIT is '123'.
    test_hit(assignment, {"AssignmentStatus": ["Approved", "Submitted"]} returns True,
    if the assignment status of assignment is Approved or Submitted.
    test_hit(hit, {"RequesterAnnotation": ["+AUDIO_DESC", "+CAPTION_EDIT"]} returns True,
    if the RequesterAnnotation of the HIT starts with either "AUDIO_DESC" or "CAPTION_EDIT".

    :param hit: HIT (or other dict) to test
    :type hit: dict[str, any]
    :param params: Parameters to test with. Parameters
    :type params: dict[str, list[any]]
    :return: True if parameters hold true, False if not
    :rtype: bool
    """

    def test_one(p, h):
        if p == '':
            return p == h
        else:
            if p[0] == '+':
                if h.startswith(p[1:]):
                    return True
            elif p[0] == '-':
                if h.endswith(p[1:]):
                    return True
            else:
                return p == h

    for i in params:
        if i not in hit:
            return False
        pars = params[i]
        if any(test_one(p, hit[i]) for p in pars):
            continue
        else:
            return False

    return True


def get_answer_data(client: MTurkClient,
                    ofile: str,
                    hit_search_params: DataDict = {},
                    assignment_search_params: DataDict = {},
                    write: bool = True,
                    max_hits: int = -1,
                    stop_after_first: bool = False) \
        -> ResultDict:
    """ Get all assignment data, i.e. answers, from AMT for the given client
    and HIT and assignment search parameters.
    If write = True, also writes the results into a file.

    :param client: AMT client to use
    :type client: botocore.client.BaseClient
    :param ofile: Output file (if write = True)
    :type ofile: str
    :param hit_search_params: Filter parameters to use when fetching HITs.
    E.g. hit_search_params = {'Title': 'Hello'} fetches all HITs whose title is 'Hello'.
    :type hit_search_params: dict[str, any]
    :param assignment_search_params: Filter parameters to use when fetching assignments.
    E.g. assignment_search_param = {'AssignmentStatus': 'Approved'} fetches all assignments
    whose AssignmentStatus is 'Approved'.
    :type assignment_search_params: dict[str, any]
    :param write: Whether to write the results into a file
    :type write: bool
    :param max_hits: Max number of HITs to fetch. < 0 for no limit.
    :type max_hits: int
    :param stop_after_first: Whether to stop fetching HITs on the first HIT
    satisfying hit_search_params.
    :type stop_after_first: bool
    :return: The assignments fetched from AMT. The format is a dict with a key for each
    column with the value being a list of the rows in that column.
    I.e. results['AssignmentStatus'][10] is the value of 'AssignmentStatus' of the
    11th assignment.
    :rtype: dict[str, list[str]]
    """
    header = ['HITId', 'Title', 'AssignmentId', 'WorkerId', 'AssignmentStatus', 'RejectionTime', 'RequesterAnnotation']
    answer_names = []
    results = {}

    try:
        assignments, hit_data = get_all_assignments(
            client,
            hit_search_params=hit_search_params,
            assignment_search_params=assignment_search_params,
            max_hits=max_hits,
            stop_after_first_hit=stop_after_first
        )
    except TypeError:
        print('Invalid search parameters!')
        return

    # Get all answer names from data
    for assignment in assignments:
        answers = xmltodict.parse(assignment['Answer'])['QuestionFormAnswers']['Answer']
        for answer in answers:
            var_name = answer['QuestionIdentifier']
            if var_name not in header and var_name not in answer_names:
                answer_names.append(var_name)

    for h in header:
        results[h] = []
    for name in answer_names:
        results[name] = []
    for assignment in assignments:
        hit = hit_data[assignment['HITId']]
        answers = xmltodict.parse(assignment['Answer'])['QuestionFormAnswers']['Answer']

        for h in header:
            if h in hit:
                results[h].append(hit[h])
            elif h in assignment:
                results[h].append(assignment[h])
            else:
                results[h].append("")

        for answer in answers:
            var_name = answer['QuestionIdentifier']
            val = ''
            for key in answer:
                if key != 'QuestionIdentifier':
                    val = answer[key]

            results[var_name].append(val)

        # Fill nonexisting answers with blank spaces
        count = len(results['HITId'])
        for name in answer_names:
            if len(results[name]) != count:
                results[name].append('')

    if write:
        write_ans_data_file(results, ofile)

    return results


def write_ans_data_file(data: ResultDict,
                        ofile: str,
                        ignore: List[str] = [],
                        select: Union[List[str], str] = []) \
        -> None:
    """ Write a csv file from the given data

    :param data: Data to write to csv
    :type data: dict[str, list[str]]
    :param ofile: Output file path
    :type ofile: str
    :param ignore: List of keys (columns) to ignore
    :type ignore: list[str]
    :param select: List of keys (columns) to select or 'score' to select keys associated
    with the score task. Selects all keys by default.
    :type select: list[str] or str
    """
    if select == []:
        select = list(data.keys())
    elif select == 'score':
        select = ['HITId', 'Title', 'AssignmentId', 'WorkerId', 'assignments', 'audioUrl', 'captions',
                  'accuracy_scores', 'fluency_scores', 'Feedback']

    Path(ofile).parent.mkdir(exist_ok=True, parents=True)

    with open(ofile, 'w', newline='\n') as f:
        writer = csv.writer(f, delimiter=',')
        titles = [i for i in select if i not in ignore and i in data]
        writer.writerow(titles)

        for i in range(len(data[titles[0]])):
            row = [data[j][i] for j in titles if j not in ignore and j in select]
            for j in range(len(row)):
                if not row[j]:
                    row[j] = u''
                else:
                    try:
                        row[j] = str(row[j]).encode('ASCII').decode()
                    except:
                        # Replace non-ASCII characters with ASCII characters, e.g. á -> a.
                        row[j] = replace_non_ascii(row[j])

            writer.writerow(row)


def get_all_hits(client: MTurkClient,
                 hit_search_params: DataDict = {},
                 print_info: bool = True,
                 max_hits: int = -1,
                 stop_after_first: bool = False) \
        -> List[DataDict]:
    """ Fetches all HITs from AMT for given client and parameters.

    :param client: AMT client to use
    :type client: botocore.client.BaseClient
    :param hit_search_params: Filter parameters to use when fetching HITs
    :type hit_search_params: dict[str, any]
    :param print_info: Whether or not to print information to the console. (verbosity)
    :type print_info: bool
    :param max_hits: Max number of HITs to fetch. < 0 to not use any limit.
    :type max_hits: int
    :param stop_after_first: Whether or not to stop fetching on the first HIT that
    satisfies hit_search_params
    :type stop_after_first: bool
    :return: List of fetched HITs
    :rtype: list[dict[str, any]]
    """
    results = []
    gathered = 0
    processed = 0
    done = 0
    if print_info:
        print('Gathering HITs... Ctrl+C to interrupt')

    q = client.list_hits(MaxResults=100)
    try:
        while q['NumResults'] > 0:
            nt = q['NextToken']
            for hit in q['HITs']:
                if 0 < max_hits <= processed:
                    done = 1
                    break

                if print_info and processed % 100 == 0:
                    print(f'\rGathered: {gathered}\t\tProcessed: {processed}', end='', flush=True)
                processed += 1
                if not test_hit(hit, hit_search_params):
                    if gathered != 0 and stop_after_first:
                        done = 1
                        break
                    continue

                results.append(hit)
                gathered += 1

            if done:
                break
            q = client.list_hits(NextToken=nt, MaxResults=100)
    except KeyboardInterrupt:
        print(f'Interrupted by user! Got {gathered} HITs.')

    if print_info:
        print('\rGathered: %s\t\tProcessed: %s' % (gathered, processed))

    return results


def get_hit_assignments(client: MTurkClient,
                        hitid: str,
                        assignment_search_params: DataDict = {}) \
        -> List[DataDict]:
    """ Fetches all assignments for given HIT from AMT for given client and parameters

    :param client: AMT client to use
    :type client: botocore.client.BaseClient
    :param hitid: HITId of the HIT for which to fetch assignments
    :type hitid: str
    :param assignment_search_params: Filter parameters to use when fetching assignments
    :type assignment_search_params: dict[str, any]
    :return: List of fetched assignments
    :rtype: list[dict[str, any]]
    """
    results = []

    q = client.list_assignments_for_hit(HITId=hitid)
    while q['NumResults'] > 0:
        nt = q['NextToken']
        assignments = q['Assignments']
        for assign in assignments:
            if test_hit(assign, assignment_search_params):
                results.append(assign)
        q = client.list_assignments_for_hit(HITId=hitid, NextToken=nt)

    return results


def get_all_assignments(client: MTurkClient,
                        hit_search_params: DataDict = {},
                        assignment_search_params: DataDict = {},
                        print_info: bool = True,
                        max_hits: int = -1,
                        stop_after_first_hit: bool = False) \
        -> Tuple[List[DataDict], Dict[str, DataDict]]:
    """ Fetch all assignments for all HITs from AMT for given client and parameters

    :param client: AMT client to use
    :type client: botocore.client.BaseClient
    :param hit_search_params: Filter parameters to use when fetching HITs
    :type hit_search_params: dict[str, any]
    :param assignment_search_params: Filter parameters to use when fetching assignments
    :type assignment_search_params: dict[str, any]
    :param print_info: Whether to print information on the console. (verbosity)
    :type print_info: bool
    :param max_hits: Max number of HITs to fetch assignments for. < 0 for no limit.
    :type max_hits: int
    :param stop_after_first_hit: Whether to stop fetching HITs after the first one that
    satisfies hit_search_params
    :type stop_after_first_hit: bool
    :return: Tuple with list of fetched assignments and a dict with the HIT info with
    HITIds as keys
    :rtype: tuple[list[dict[str, any]], dict[str, dict[str, any]]]
    """
    results = []
    hit_data = {}
    hits = get_all_hits(
        client,
        hit_search_params=hit_search_params,
        max_hits=max_hits,
        stop_after_first=stop_after_first_hit
    )
    if print_info:
        print('Gathering assignments... Ctrl+C to interrupt.')
        cnt = 0
        size = len(hits)
    try:
        for hit in hits:
            if print_info and cnt % 10 == 0:
                print(f'\rGathered assignments from {cnt}/{size} HITs', end='', flush=True)

            hit_data[hit['HITId']] = hit
            assignments = get_hit_assignments(client, hit['HITId'])
            for assignment in assignments:
                if test_hit(assignment, assignment_search_params):
                    results.append(assignment)
            cnt += 1
    except KeyboardInterrupt:
        print(f'Interrupted by user! Got assignments for {cnt}/{size} HITs')

    return results, hit_data


def main():
    config = read_yaml('config.yaml')
    aws_keys = read_yaml('aws_keys.yaml')

    req_annotations = get_req_annotation_for_batch(config, True)

    batch_params = {
        'RequesterAnnotation': req_annotations
    }

    client = get_client(aws_keys, config)
    out_file = Path(config['CURRENT']['output_data_file'])

    if out_file.exists():
        print(f'Output file {out_file} already exists. ', end='')

        i = 1
        add_i = lambda path: path.with_name(path.stem + f'({i}){path.suffix}')
        print(f'Using out path {add_i(out_file)} instead')
        while add_i(out_file).exists():
            print(f'Output file {add_i(out_file)} already exists. ', end='')
            i += 1
            print(f'Using out path {add_i(out_file)} instead')
        out_file = add_i(out_file)

    get_answer_data(
        client, str(out_file),
        hit_search_params=batch_params
    )


if __name__ == '__main__':
    main()

# EOF
