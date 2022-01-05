import json
import os
from typing import TextIO, Hashable, Iterator

from dateutil.parser import isoparse

from utils.sorts import Sort, Group


def parse_board(f: TextIO, card_mapping: dict[str, Hashable] = None) -> Sort:
    """
    Extracts the information from a trello board json file.

    An optional card_mapping can be provided to map the card prompts to an ID
    which may be more useful for analysis. If provided, card prompts will be
    mapped to the given ID when parsing and used in place of the card prompt.

    :param f: a TextIO Stream of the trello board json file
    :param card_mapping: an optional mapping of card names to card ids
    :return: a Sort object
    """
    data = json.load(f)

    trello_lists = data['lists']
    trello_lists.sort(key=lambda x: x['pos'])

    # Cards are linked to their lists by list ID. So, a temporary mapping
    # from list IDs to groups is needed.
    groups_by_id = {}
    for trello_list in trello_lists:
        group_name = trello_list['name']
        list_id = trello_list['id']
        group = Group(group_name)
        groups_by_id[list_id] = group

    cards = data['cards']
    # Participants may accidentally add cards which are then deleted, "closed".
    cards = [card for card in cards if not card['closed']]

    for card in cards:
        group_id = card['idList']
        group = groups_by_id[group_id]
        # It may be more useful to map card prompts to an ID for analysis
        if card_mapping is not None:
            card_data = card_mapping[card['name']]
        else:
            card_data = card['name']
        group.cards.add(card_data)

    actions = data['actions']
    actions.sort(key=lambda x: isoparse(x['date']))

    # Only card moves, list creation, and list renaming are considered.
    valid_actions = []
    for action in actions:
        action_data = action['data']
        action_type = action['type']
        # Card is moved
        if action_type == 'updateCard' and 'listBefore' in action_data:
            valid_actions.append(action)
        # List is created
        elif action_type == 'createList':
            valid_actions.append(action)
        # List is renamed
        elif action_type == 'updateList' and 'name' in action_data['old']:
            valid_actions.append(action)

    # For the purposes of this study, sorts were considered to start when the
    # first trello list was created. Sorts were considered to end when the
    # last card move or list rename action was performed.
    first_list = next(action for action in valid_actions
                      if action['type'] == 'createList')
    start_time = isoparse(first_list['date'])
    end_time = isoparse(actions[-1]['date'])
    total_sort_time = end_time - start_time

    # Empty groups are discarded.
    groups = [group for group in groups_by_id.values() if group.cards]

    sort_name = data['name']
    sort = Sort(sort_name, groups, total_sort_time)
    return sort


def get_paths_to_jsons_in_dir(path: str) -> Iterator[str]:
    """
    Returns a list of paths to json files in the given directory. Nested
    directories are not traversed.

    :param path: a path to a directory
    :return: the list of paths to json files in the given directory
    """
    files = os.listdir(path)
    for file in files:
        file_path = os.path.join(path, file)
        if os.path.isfile(file_path) and file.endswith('.json'):
            yield file_path


def parse_sorts_in_dir(path: str,
                       card_mapping: dict[str, Hashable] = None) -> list[Sort]:
    """
    Parses all sorts in the given directory. Nested directories are not
    traversed. This is equivalent to calling parse_sort on each json file in
    the given directory.

    :param path: a path to a directory
    :param card_mapping: an optional mapping of card names to card ids
    :return: a list of Sort objects
    """
    sorts = []
    trello_json_paths = get_paths_to_jsons_in_dir(path)
    for path in trello_json_paths:
        with open(path, 'r') as f:
            sort = parse_board(f, card_mapping)
            sorts.append(sort)
    return sorts
