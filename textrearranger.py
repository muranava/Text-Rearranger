#!usr/bin/python

"""Re-write a text stream based on word topology"""

from __future__ import print_function#, unicode_literals

import random
import options
import copy
import time
import cProfile


def tokenizer(f):
    """Iterator that yields every word from a given open file"""
    for line in f:
        for word in line.split(" "):
            yield word


def check_speed(cmd):
    """Slow down the program as user defined"""
    if cmd["slow_output"]:
        time.sleep(cmd["slow_speed"])


def jabberwocky(first, second):
    """Jabberwocky two given words together"""
    if first == second:
        return first
    nFirst = 0
    nSecond = 0
    newWord = ""
    # gives precedence to starting with the second word
    do = (len(second) + 1) % 4
    while nFirst < len(first):
        if do in (0, 1):
            newWord += first[nFirst]
        elif do in (2, 3):
            newWord += second[nSecond]
        nFirst += 1
        nSecond = (nSecond + 1) % len(second)
        do = (do + 1) % 4
    return newWord


def fill_word_map(cmd, wordMap):
    """Fill a given wordMap with contents from a wordMap file"""
    for line in cmd["word_map"]:
        line = line.strip()
        words = line.split(" ")
        try:
            wordMap[words[0]] = " ".join(map(str, words[1:]))
        except Exception:
            print("ISSUE: Wrong word map file syntax at line \"%s\"" % line)


def get_metadata(cmd, word):
    """Parse out metadata for a word, based on command settings"""

    if cmd["compare_lower"]:
        word = word.lower()

    if not cmd["compare_case"]:
        case = ""
    elif word.istitle():
        case = "title"
    elif word.islower():
        case = "lower"
    elif word.isupper():
        case = "upper"
    else:
        case = "mixed"

    if cmd["first_letter"] and len(word) >= 1:
        letter = word[0]
        if not cmd["case_sensitive"]:
            letter = letter.lower()
    else:
        letter = ""

    if cmd["length_check"]:
        length = len(word)
    else:
        length = 0

    return case, letter, length


def get_punctuation_point(word, start, step):
    """Return the point at which non-word punctuation ends"""
    letter = start
    while (letter < len(word) and letter >= 0 and not word[letter].isalnum()):
        letter += step
    return letter


def parse_punctuation(cmd, word):
    """
    Return the punctuation before the word, the stripped down word,
    and the punctuation after the word
    """
    puncBefore = ""
    puncAfter = ""

    if cmd["soft_truncate_newlines"] or cmd["hard_truncate_newlines"]:
        word = word.strip()
    if cmd["preserve_punctuation"]:
        cutoff = get_punctuation_point(word, 0, 1)
        if not cmd["void_outer"]:
            puncBefore = word[:cutoff]
        word = word[cutoff:]

        cutoff = get_punctuation_point(word, len(word) - 1, -1)
        # the last letter is the default target
        cutoff += 1
        if not cmd["void_outer"]:
            puncAfter = word[cutoff:]
        elif word and word[-1] == "\n":
            puncAfter += word[-1]
        word = word[:cutoff]
    # split newlines from word
    elif word:
        if word[-1] == "\n":
            word = word[:-1]
            puncAfter = "\n"

    if cmd["void_inner"]:
        temp = ""
        for c in word:
            if c.isalnum():
                temp += c
        word = temp

    return puncBefore, word, puncAfter


def fill_dictionary(cmd, dictionary, filterList, source="source"):
    """
    Fill a dictionary sorted by case, leading letter, and length
    Each word is filtered by its' metadata, which depends on cmd arguments
    Will optionally filter the dictionary as it builds it
    Also returns the count of each word, and total word count
    """

    occurences = {}
    wordCount = 0
    for word in tokenizer(cmd[source]):

        _, word, _ = parse_punctuation(cmd, word)
        # source file should not be filtered except by request
        if (not word or cmd["filter_source"] and
                not check_filter(cmd, filterList, word)):
            continue
        case, letter, length = get_metadata(cmd, word)

        if not dictionary.get(case):
            dictionary[case] = {}
        if not dictionary[case].get(letter):
            dictionary[case][letter] = {}
        if not dictionary[case][letter].get(length):
            dictionary[case][letter][length] = []

        dictionary[case][letter][length].append(word)
        if not occurences.get(word):
            occurences[word] = 0
        occurences[word] += 1
        wordCount += 1

    return occurences, wordCount


def sort_dictionary(cmd, dictionary):
    """Sorts a given dictionary based on commands"""

    uniqueOnly = False
    shuffle = False
    alphabetical = cmd["alphabetical_sort"]

    if (cmd["equal_weighting"] or cmd["map_words"] or
            cmd["pure_mode"] and 
            (cmd["filter_same"] or cmd["filter_different"])):
        uniqueOnly = True
    if cmd["limited_usage"] and not cmd["block_shuffle"]:
        shuffle = True

    for case in dictionary:
        for letter in dictionary[case]:
            for length in dictionary[case][letter]:
                wordList = dictionary[case][letter][length]
                if uniqueOnly:
                    wordList = list(set(wordList))
                # randomizes words pulled later
                if shuffle:
                    random.shuffle(wordList)
                if alphabetical:
                    wordList = sorted(wordList, key=str.lower)
                    wordList.reverse()
                dictionary[case][letter][length] = wordList


def check_filter(cmd, filterList, word):
    """
    Check a word against a filter list and filter type
    Return true if word should be filtered, false otherwise
    """
    if not cmd["filter_same"] or cmd["filter_different"]:
        return False
    if cmd["compare_lower"]:
        word = word.lower()
    found = word in filterList
    if ((cmd["filter_same"] and found) or
        (cmd["filter_different"] and not found)):
        return True
    else:
        return False


def get_filter_list(cmd):
    """Return a formatted filter list of words to compare against"""
    filterList = set([])
    if not (cmd["filter_same"] or cmd["filter_different"]):
        return filterList
    for word in tokenizer(cmd["filter"]):
        _, word, _ = parse_punctuation(cmd, word)
        if cmd["compare_lower"]:
            word = word.lower()
        filterList.add(word)
    return filterList


def search_dictionary(dictionary, level, sort, wordData, indent=0, order=None):
    """Recursively enter each level of a dictionary to find all contents"""

    output = []
    newIndent = indent

    if not order:
        order = dictionary.keys()
        order = sorted(order)

    for section in order:
        if section not in dictionary:
            continue
        if section:
            output.append("%s%s %s" % (
                " " * indent, level[0], section))
            newIndent = indent + 2
        if isinstance(dictionary[section], dict):
            output += search_dictionary(dictionary[section], level[1:], 
                                        sort, wordData, newIndent)
        else:
            wordList = dictionary[section]
            wordList = list(set(wordList))
            if sort:
                wordList = sorted(wordList, key=str.lower)
            for word in wordList:
                line = "%s%s" % (" " * newIndent, word)
                data = wordData.get(word)
                if data["str"]:
                    line += " %s" % data["str"]
                output.append(line)

    return output


def create_word_data(cmd, occurences, wordCount):
    """
    Return wordData, amalgamating word statistics and info strings
    """

    wordData = {}
    # percent values need to be float
    wordCount *= 1.0

    for word, count in occurences.items():

        data = {"str": "{"}
        data["count"] = count
        data["percent"] = count / wordCount * 100
        if cmd["frequency_count"]:
            data["str"] += "count: %d" % count
            if cmd["frequency_percent"]:
                data["str"] += ", "
        if cmd["frequency_percent"]:
            percent = "frequency: {:." + str(cmd["decimal_accuracy"]) + "%}"
            data["str"] += percent.format(count / wordCount)
        data["str"] += "}"
        # ie if nothing was added
        if data["str"] == "{}":
            data["str"] = ""
        wordData[word] = data

    return wordData


def limit_dictionary(cmd, dictionary, wordData):
    """Limit a dictionary based on wanted word counts"""

    for case in dictionary:
        for letter in dictionary[case]:
            for length in dictionary[case][letter]:
                wordList = dictionary[case][letter][length]
                newWordList = []
                for word in wordList:
                    count = wordData[word]["count"]
                    percent = wordData[word]["percent"]
                    if (count >= cmd["count_minimum"] and
                            count <= cmd["count_maximum"] and
                            percent >= cmd["percent_minimum"] and
                            percent <= cmd["percent_maximum"]):
                        newWordList.append(word)
                    dictionary[case][letter][length] = newWordList

    temp = copy.deepcopy(dictionary)
    for case in temp:
        for letter in temp[case]:
            for length in temp[case][letter]:
                if len(dictionary[case][letter][length]) == 0:
                    dictionary[case][letter].pop(length)
            if len(dictionary[case][letter]) == 0:
                dictionary[case].pop(letter)
        if len(dictionary[case]) == 0:
            dictionary.pop(case)


def generate_analysis(cmd, dictionary, occurences, wordCount):
    """Generates an analysis of statistics for dictionary findings"""

    output = []
    wordData = create_word_data(cmd, occurences, wordCount)
    limit_dictionary(cmd, dictionary, wordData)

    order = ["upper", "title", "lower", "mixed", ""]
    level = ["Case", "Letter", "Length"]
    sort = not cmd["block_inspection_sort"]
    output = search_dictionary(dictionary, level, sort, wordData, order=order)
    for line in output:
        check_speed(cmd)
        cmd["output"].write(line + "\n")


def get_word_list(cmd, dictionary, word):
    """Sort through a dictionary to find a matching wordList, if any"""
    wordList = dictionary
    for layer in get_metadata(cmd, word):
        wordList = wordList.get(layer)
        if not wordList:
            return []
    return wordList


def get_random_word(wordList):
    """Get a random word from a given wordList"""
    return wordList[random.randint(0, len(wordList) - 1)]


def find_replacement(cmd, dictionary, wordMap, word):
    """
    Try to get a suitable replacement word
    Return an empty string if no replacement can be found
    Update wordMap along the way as needed
    """

    wordList = get_word_list(cmd, dictionary, word)
    if not wordList:
        newWord = ""
    elif cmd["alphabetical_sort"]:
        newWord = wordList.pop()
    elif len(wordList) == 1:
        newWord = wordList[0]
    elif cmd["map_words"] or cmd["get_different"]:
        newWord = word
        attempts = 0
        while newWord == word and attempts < cmd["get_attempts"]:
            newWord = get_random_word(wordList)
            attempts += 1
        if cmd["limited_usage"] or cmd["map_words"]:
            wordList.remove(newWord)
    elif cmd["equal_weighting"] or cmd["relative_usage"]:
        newWord = get_random_word(wordList)
    # falls back on limited usage
    else:
        # popping from the end means less memory usage
        newWord = wordList.pop()

    if cmd["map_words"]:
        # print(wordList)
        wordMap[word] = newWord
    elif (cmd["force_limited_usage"] and not cmd["limited_usage"] and
            word in wordList):
        wordList.remove(word)

    return newWord


def get_new_word(cmd, dictionary, filterList, wordMap, word):
    """Get a new word from any possible method"""
    passedFilter = check_filter(cmd, filterList, word)
    result = wordMap.get(word)
    if cmd["pure_mode"] and not passedFilter:
        newWord = ""
        # print("pure filter failure: %s" % word)
    elif passedFilter:
        newWord = word
        # print("filter success: %s" % word)
    elif result:
        newWord = result
        # print("word map success: %s from %s" % (result, word))
    elif cmd["halt_rearranger"]:
        newWord = word
        # print("rearranger halted: %s" % word)
    else:
        newWord = find_replacement(cmd, dictionary, wordMap, word)
        # print("replaced: %s with %s" % (word, newWord))
    return newWord


def generate_text(cmd, dictionary, filterList, wordMap):
    """Rearrange or filter the input text to create a new output"""

    output = []
    line = ""
    for word in tokenizer(cmd["input"]):

        if word == "\n":
            if (not cmd["hard_truncate_newlines"] and
                    not (cmd["truncate_multiple_newlines"] and
                        len(output) >= 2 and
                        output[-1][-1] == "\n" and
                        output[-2][-1] == "\n")):
                output.append("\n")
            continue
        if word == "":
            if not cmd["truncate_whitespace"]:
                line += " "
            continue

        puncBefore, word, puncAfter = parse_punctuation(cmd, word)
        line += puncBefore
        if word:
            newWord = get_new_word(cmd, dictionary, filterList, wordMap, word)
            if (cmd["jabberwocky"] and 
                    random.randint(0, 99) < cmd["jabberwocky_chance"]):
                newWord = jabberwocky(word, newWord)
                # print("jabbered! %s" % newWord)
            line += newWord
        line += puncAfter
        if (not cmd["hard_truncate_newlines"] and 
                random.randint(0, 99) < cmd["kick_chance"]):
            line += "\n"
        elif line and line[-1] != "\n" and not cmd["truncate_whitespace"]:
            line += " "
        else:
            # remove trailing spaces
            output.append(line.replace(" \n", "\n"))
            line = ""

    output.append(line)
    for line in output:
        check_speed(cmd)
        cmd["output"].write(line)
    # ensures one newline at the end of the output
    if not cmd["hard_truncate_newlines"] and (line and line[-1] != "\n"):
        cmd["output"].write("\n")


def main():
    """Run the program"""

    cmd = options.get_command()
    if cmd["random_seed"] != -1:
        random.seed(cmd["random_seed"])

    wordMap = {}
    if cmd["word_map"]:
        fill_word_map(cmd, wordMap)
    filterList = get_filter_list(cmd)
    dictionary = {}
    occurences, wordCount = fill_dictionary(cmd, dictionary, filterList)
    sort_dictionary(cmd, dictionary)

    if cmd["inspection_mode"]:
        generate_analysis(cmd, dictionary, occurences, wordCount)
    else:
        generate_text(cmd, dictionary, filterList, wordMap)

    for f in ("input", "source", "filter", "word_map", "output"):
        if type(cmd[f]) == file:
            cmd[f].close()

main()