#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Module for expanding contractions in english text. """

__author__ = "Yannick Couzinié"

# standard library imports
import itertools
import operator
import yaml
# third party library imports
import nltk
# local imports
import utils


def _extract_contractions(sent):
    """
    Args:
        sent - a single sentence split up into (word, pos) tuples.
    Returns:
        List with the indices in the sentence where the contraction
        starts.
        Or None if no contractions are in the sentence.

    Based on the POS-tags and the existence of an apostrophe or not,
    extract the existing contractions.
    """
    idx_lst = []
    for i, word_pos in enumerate(sent):
        # If the word in the word_pos tuple begins with an apostrophe,
        # add the index to idx_list.
        if word_pos[0][0] == "'":
            if word_pos[1] != 'POS':
                # a case we can immediately dismiss is possessive
                # pronouns like "Peter's house", in which the apostrophe
                # denotes possession and not contraction.
                idx_lst.append(i)
        elif word_pos[0] == "n't":
            # if it is the special case of n't add it immediately
            idx_lst.append(i)
    if idx_lst:
        # empty list is false so use that, otherwise give no return.
        return idx_lst


def _consecutive_sub_list(int_list):
    """
    Args:
        - int_list is a list whose consecutive sub-lists are yielded
          from this function.
    Yields:
        - The consecutive sub-lists

    This is basically an adaptation from
    https://docs.python.org/2.6/library/itertools.html#examples for
    Python 3.
    """
    # we group the items by using the lambda-function for the key which
    # checks whether the next element and the current element is one
    # apart. If it it is exactly one, the list of items that are 1 apart
    # are grouped.
    # The map with the itemgetter then maps the grouping to the actual
    # items and then we yield the sublists.
    for _, index in itertools.groupby(enumerate(int_list),
                                      lambda x: x[1]-x[0]):
        yield list(map(operator.itemgetter(1), index))


def _disambiguate(sent, rplc_tuple, disambiguations, add_tags,
                  argmax=True):
    """
    Args:
        - sent is the same sentence as in rplc_tuple but with the
          pos_tags.
        - rplc_tuple is the tuple containint the index of replacement,
          the suggested replacements and the sentence.
        - disambiguations dictionary
        - add_tags is the amount of additional tags in the disambi
        - in case the disambiguation case is also ambiguous use the case
          with more occurences in the corpus. If that still doesn't help
          don't change the input.
    Returns:
        - the expanded sentence (as far as unambiguous).

    Use the disambiguation dictionary to disambiguate the expansions.
    """
    # first we need to check again whether the first word is capitalized
    if sent[0][0][0].isupper() and sent[0][0][0] != "<NE>":
        capitalized = True
        sent[0] = (sent[0][0].lower(), sent[0][1])
    else:
        capitalized = False
    # make the input tuple which is of the form of the dictionary keys
    inp_tuple = [sent[i] for i in rplc_tuple[0]]
    # append the pos tags for the rest
    inp_tuple += [sent[i][1] for i in range(rplc_tuple[0][-1]+1,
                                            rplc_tuple[0][-1]+1+add_tags)]
    inp_tuple = tuple(inp_tuple)

    if inp_tuple in disambiguations:
        if len(disambiguations[inp_tuple].keys()) == 1:
            # if this is unambiguous just handle it
            replacement = list(disambiguations[inp_tuple])[0]
        else:
            if not argmax:
                # if one should not take the argmax just replace nothing. This
                # is not recommended, but in the future it might be interesting
                # to differentiate the cases.
                replacement = []
            # if it is ambiguous find the case with the most occurences
            max_val = max(disambiguations[inp_tuple].values())
            if list(disambiguations[inp_tuple].values()).count(max_val) == 1:
                # if there is exactly one replacement with the highest
                # value, choose that
                for key, value in disambiguations[inp_tuple].items():
                    if value == max_val:
                        replacement = key
                        break
            else:
                # if it is still ambigious just stop at this point and
                # work on the disambiguations dictionary.
                replacement = []
    else:
        # if the case is not even in the dictionary just skip it and
        # work on the disambiguations dictionary.
        replacement = []
    # now do the replacements
    sent = _remove_pos_tags(sent)
    if replacement != []:
        for i, index in enumerate(rplc_tuple[0]):
            sent[index] = replacement.split()[i]

    if capitalized:
        sent[0] = sent[0].title()
    return sent


def _extract_replacements(idx_lst, sent, contractions):
    """
    Args:
        idx_lst - The list of indices for the position of contractions
                  in sent.
        sent - List of (word, pos) tuples.
        contractions - dictionary of contractions in the form of:
                            'contracted string' : 'list of possible
                                                   replacements'
    Returns:
        A list in the form of (tuples of (index of words to be replaced,
                                          word to be replaced,
                                          list of suggested replacements))
        Examples are: ([0,1], ["I", "'m"], ["I", "am"])
            ([0,1], ["She", "'s"], [["She", "is"], ["She", "has"]])

    Based on the idx_lst and the contractions dictionary, give a list of
    replacements which shall be performed on the words in sent.
    """
    # loop over all the consecutive parts
    for consecutive in _consecutive_sub_list(idx_lst):
        # add the one index prior to the first one for easier
        # replacements
        consecutive = [consecutive[0]-1] + consecutive
        # combine all the words that are expanded, i.e. one word
        # before the first apostrophe until the last one with an
        # apostrophe
        contr = [word_pos[0] for word_pos
                 in sent[consecutive[0]:consecutive[-1]+1]]
        # if the expanded string is one of the known contractions,
        # extract the suggested expansions.
        # Note that however many expansions there are, expanded is a list!
        if ''.join(contr) in contractions:
            expanded = contractions[''.join(contr)]
        # the dictionary only contains non-capitalized replacements,
        # check for capitalization
        elif ''.join(contr).lower() in contractions:
            if ''.join(contr)[0].isupper():
                # capitalize the replacement in this case
                expanded = [a.capitalize() for a in
                            contractions[''.join(contr).lower()]]
        else:
            # if the replacement is unknown skip to the next one
            print("WARNING: Unknown replacement: ", ''.join(contr))
            continue

        # separate the phrases into their respective words again.
        expanded = [nltk.word_tokenize(a) for a in expanded]
        yield (consecutive, contr, expanded)


def _remove_pos_tags(sent):
    """
    Args:
        sent - list of (word, pos) tuples
    Returns:
        A list of only lexical items.

    Convert a list of (word, pos) tuples back to a list of only words.
    """
    output = []
    for word_pos in sent:
        output.append(word_pos[0])
    return output


def expand_contractions(stanford_model,
                        sent_list,
                        is_split=True,
                        use_ner=False,
                        ner_args=None):
    """
    Args:
        stanford_model - object of StanfordPOSTagger, as returned by
                         load_stanford_pos.
        sent_list - list of sentences which are split up by word.
                    For the splitting use nltk.word_tokenize.
        is_split - boolean to track whether splitting has to be done
                   or not. If it has to be done provide sentences as
                   single strings.
        use_ner - boolean to decide whether to use
                  named-entity-recognition for a potential increase in
                  accuracy but with the obvious costs of performance.
        ner_args - is a list with an  object of StanfordNERTagger and
                   the tag to be used. This only needs to be
                   supplied if use_ner is true.
    Returns:
        sent_list with expanded contractions.

    Raises:
        ValueError if use_ner is True but no ner_model is supplied.

    This method uses the StanfordPOSTagger tags to identify contractions in
    the sentence and expand them sensibly. Some examples are:
        "I'm" -> "I am"
        "It's difficult" -> "It is difficult"
    The difficulty is that sometimes "'s" is not an indicator of a
    contraction but a possessive pronoun like
        "It's legs were shaking"
    which should not be expanded. The stanford tagger tags this as
    "POS" for possessive which makes it easy to identify these cases.
    Furthermore, a difficulty lies in the fact that the expansion is not
    unique. Without context we have for example the following:
        "I'll" -> "I will" or "I shall"
    """
    if use_ner and (ner_args is None):
        raise ValueError("The use_ner flag is True but no NER"
                         " model has been supplied!")

    with open("contractions.yaml", "r") as stream:
        # load the dictionary containing all the contractions
        contractions = yaml.load(stream)

    with open("disambiguations.yaml", "r") as stream:
        disambiguations = yaml.load(stream)

    # first we need to check how many additional tags there are
    # for that take the first element of the keys list of the
    # dictionary
    add_tags = 0
    for element in list(disambiguations)[0]:
        # if the type is str and not tuple it is an additional tag
        if isinstance(element, str):
            add_tags += 1

    output = []
    # look at all the sentences in the list
    for word_pos_ner in utils.conv_2_word_pos(stanford_model,
                                              sent_list,
                                              is_split=is_split,
                                              use_ner=use_ner,
                                              ner_args=ner_args):
        if use_ner:
            # the actual sentence is just the first element, the second
            # one is the list of strings that were replaced (i.e. the
            # named-entities).
            sent = word_pos_ner[0]
        else:
            sent = word_pos_ner

        # get all the indices of the contractions
        idx_lst = _extract_contractions(sent)
        tmp = _remove_pos_tags(sent)
        if idx_lst is None:
            # if there are no contractions, continue
            sent = tmp
        else:
            # evaluate the needed replacements, and loop over them
            for rplc_tuple in _extract_replacements(idx_lst,
                                                    sent,
                                                    contractions):

                # if the replacement is unambiguous, do it.
                if len(rplc_tuple[2]) == 1:
                    for i, index in enumerate(rplc_tuple[0]):
                        tmp[index] = rplc_tuple[2][0][i]
                    sent = tmp
                else:
                    # else deal with the ambiguous case
                    sent = _disambiguate(sent, rplc_tuple,
                                         disambiguations, add_tags)
        output.append(sent)
        # at this point there is definetly the next item added to
        # output. So just replace the NER-tag now
        if use_ner:
            # just replace it in the last element
            output[-1] = utils.ner_to_sent(output[-1],
                                           word_pos_ner[1],
                                           tag=ner_args[1])
    if not is_split:
        # join the sentences if they were joined in the beginning
        output = [' '.join(sent) for sent in output]
        # remove the space in front of the apostrophe, if it survived
        # the apostrophe cleansing.
        output = [sent.replace(" '", "'") for sent in output]
    return output


if __name__ == '__main__':
    TEST_CASES = [
        "I won't let you get away with that",  # won't ->  will not
        "I'm a bad person",  # 'm -> am
        "It's his cat anyway",  # 's -> is
        "It's not what you think",  # 's -> is
        "It's a man's world",  # 's -> is and 's possessive
        "Catherine's been thinking about it",  # 's -> has
        "It'll be done",  # 'll -> will
        "Who'd've thought!",  # 'd -> would, 've -> have
        "She said she'd go.",  # she'd -> she would
        "She said she'd gone.",  # she'd -> had
        "Y'all'd've a great time, wouldn't it be so cold!"
        # Y'all'd've -> You all would have, wouldn't -> would not
        ]
    # use nltk to split the strings into words
    POS_MODEL = utils.load_stanford(model='pos')
    NER_MODEL = utils.load_stanford(model='ner')
    # expand the sentences
    EXPANDED_LIST = expand_contractions(POS_MODEL,
                                        TEST_CASES,
                                        is_split=False,
                                        use_ner=True,
                                        ner_args=[NER_MODEL, "<NE>"])
    for SENT in EXPANDED_LIST:
        print(SENT)
