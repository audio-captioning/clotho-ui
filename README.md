# Clotho Annotation UI via AMT

Welcome to the Clotho Annotation UI repository.

This repository contains the code to gather audio captioning (descriptions of audio samples) annotations on Amazon 
Mechanical Turk (AMT) using a three-task structure according to our paper

S. Lipping, K. Drossos, T.Virtanen, "Crowdsourcing a Dataset of Audio Captions," in proceedings of the Detection and
Classification of Acoustic Scenes and Events (DCASE) Workshop, N.Y., U.S.A., 2019 

The paper can be found online: [https://arxiv.org/abs/1907.09238](https://arxiv.org/abs/1907.09238).
**If you use our code, please cite the paper**.

The three tasks are: 

  1. audio description, 
  2. caption editing, and 
  3. caption scoring.

In audio description, initial captions are gathered for the audio samples that we are using. Five captions are 
gathered for each audio sample.

In caption editing, the initial captions are edited to remove any typos or other similar problems. 
Each initial caption is edited once.

In caption scoring, the initial and edited captions are scored based on accuracy and fluency. Each set of captions 
is scored three times.

The scores can then be used to sort the captions to choose the best captions as the final annotations.

In order to ensure that a worker does not end up seeing their own submissions from earlier tasks (e.g. scoring their
own description from the audio description task), the audio files and HITs should be divided into 10 batches.
Each worker will then be allowed to participate in one task per batch. This can be accomplished using custom AMT
qualifications. Once a batch of a given task is finished, the bath qualification should then be granted to the workers
who participated in the task in that batch.

----

## Requirements

To use this repository, you must have the following packages installed in Python:

- boto3 v1.11.3
- tqdm v4.40.2
- PyYAML v5.1.2
- xmltodict v0.12.0

----

## Files

The `data` folder contains the input and output files generated by the scripts. The input file must be created 
by the user. The folder also contains templates for the `aws_keys.yaml` and `custom_qualifications.yaml` files.

The `tasks` folder contains the HIT layout HTML files of each of the three tasks: 
[Audio Description](tasks/Audio_description.html), [Caption Editing](tasks/Edit_caption.html), 
and [Caption Scoring](tasks/Score_captions.html). These were copied directly from the HTML editor in the 
requester page of AMT.

`config.yaml` contains the settings used by the script and the attributes of the HITs of each of the three tasks.

`create_hit.py` is a script that publishes HITs on AMT according to the config file.

`get_results.py` is a script that fetches results of the task determined in the config file from AMT.

`tools.py` contains some helper functions used by both scripts.

`aws_keys.yaml` will contain your AWS API keys.

`custom_qualifications.yaml` will contain Qualification information used by AMT for requirements.

----

## Getting started

1) In the HTML file `tasks/Audio_description.html`, replace the placeholders
 `YOUR_EXAMPLE_1_FILE_HERE` and `YOUR_EXAMPLE_2_FILE_HERE` with your example audio files.
 Also replace the respective example descriptions to match.

2) Go to [https://uniqueturker.myleott.com/](https://uniqueturker.myleott.com/) and create 10 unique identifiers 
(one for each batch) for 100 HITs/worker and copy them to the `config.yaml` file in the field `UNIQUE_IDS`.

3) On the same page ([https://uniqueturker.myleott.com/](https://uniqueturker.myleott.com/)) create two
identifiers for 1 HIT/worker and copy them to the `config.yaml` file in the fields
`TASKS.AUDIO_DESC.collapse_instructions_token` and `TASKS.CAPTION_EDIT.collapse_instructions_token`.
These will be used to collapse the instructions if a worker has already participated in the HITs before
to avoid inconvenient scrolling.

4) Copy your access ID and secret key into an `aws_keys.yaml` file under the fields 
`access_key_id` and `secret_access_key`. 
If you do not have these yet, create them by following the steps in 
[https://requester.mturk.com/developer](https://requester.mturk.com/developer).

(The script will detect and/or create batch qualifications and a blacklist qualification and write 
`custom_qualifications.yaml` automatically. If you would rather create these yourself or use your own qualifications, 
this file also has to be created containing the Qualfication Type IDs for
the batch qualifications and the blacklist qualification.)

7) Create an input csv file and write the file name into `config.yaml` `CURRENT.input_data_file`. 
In the file, one column represents an input parameter and each row one HIT. 
Input (and output) parameters are listed below. 
Unique IDs for batches and collapsing instructions will be added in the
script and do not need to be included in the file. 
If audioType is audio/wav, this will also be added automatically.

7) Change the `CURRENT` field data to fit your batch and run `create_hit.py`. 
This will start publishing HITs according to the settings files. 
AMT Sandbox is used by default.

8) To get submission data from AMT based on the `CURRENT` field data, run `get_results.py`. 
The data will be written in the file listed in `CURRENT.output_data_file`.

Once you have received the results for a task in a given batch, the workers who participated in that task
should be granted the appropriate qualification. E.g. once all the results have been gathered for the
batch 5 audio description task, the workers who participated in the batch 5 audio description task should
be granted the batch 5 qualification. The batch 5 qualification ID is the fifth ID in the list in the field
`BATCH` in the file `custom_qualifications.yaml`.

HIT data such as rewards can be changed in the config file. 
If you want to use task-specific requirements, you can copy the `REQUIREMENTS` field into the 
task field directly, as is done in the `CAPTION_SCORE` task.

The task layouts in tasks are treated as html documents by AMT and can be altered as such. 

## Task parameters

The input and output parameters of each task are as follows (automatically added input parameters written in parentheses):

    Audio description:
        Input:
            audioUrl - The url from which the audio is streamed, e.g. a dropbox share link.
            audioType - The format of the audio, e.g. audio/wav
            
            (unique_id - The unique turker ID from https://uniqueturker.myleott.com/ to use for the batch)
            (collapse_token - The unique turker ID from https://uniqueturker.myleott.com/ to use for collapsing instructions)
            
        Output:
            audioUrl - Same as above
            audioType - Same as above
            DescriptionText - Caption annotation from worker
            Feedback - Optional feedback from the worker

    Caption editing
        Input:
            audioUrl - The url of the audio file the caption of which is to be edited
            audioType - The format of the audio file ...
            DescriptionText - Caption annotation from the corresponding audio description assignment
            AssignmentId - AssignmentId of the assignment from which the caption annotation (DescriptionText) was acquired
            
            (unique_id - The unique turker ID from https://uniqueturker.myleott.com/ to use for the batch)
            (collapse_token - The unique turker ID from https://uniqueturker.myleott.com/ to use for collapsing instructions)
            
        Output:
            audioUrl - Same as above
            audioType - Same as above
            og_assign - AssignmentId from inputs
            ed_assign - AssignmentId of the caption editing assignment
            OriginalCaption - DescriptionText from inputs
            EditedCaption - Edited caption annotation from worker
            Feedback - Optional feedback from worker

    Caption scoring
        Input:
            audioUrl - The url from which the audio is streamed, e.g. a dropbox share link.
            audioType - The format of the audio file, e.g. "audio/wav"
            captions - Caption annotations from previous tasks. Captions are separated by "|"
            assignments - AssignmentIds of the assignments from which the captions in "captions" were gathered. Also separated by "|"
            
            (unique_id - The unique turker ID from https://uniqueturker.myleott.com/ to use for the batch)
            
        Outputs:
            audioUrl - Same as above
            audioType - Same as above
            captions - Same as above
            fluency_scoreX - E.g. fluency_score4 is the fluency score given for the fourth caption by the worker.
            accuracy_scoreX - E.g. accuracy_score4 is the accuracy score given for the fourth caption by the worker.
            fluency_scores - Fluency scores given to the captions by the worker, separated by "|"
            accuracy_scores - Accuracy scores given to the captions by the worker, separated by "|"
            Feedback - Optional feedback from the worker

This code is maintained by [lippings](https://github.com/lippings).
