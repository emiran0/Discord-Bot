import requests

# Wordle API info : https://gitlab.com/MoofyWoofy/wordle-api
def get_today_word():

    url = 'https://wordle-api-kappa.vercel.app/answer'
    response = requests.get(url)
    data = response.json()
    return data['word']
print(get_today_word())
def get_wordle_guess(word):

    url = f'https://wordle-api-kappa.vercel.app/{word}'
    response = requests.post(url)
    data = response.json()

    
    # validGuess = True or False
    # correctGuess = True or False
    # letterGueestypeId = not in word list(0), in word list but incorrect position(1), in word list and correct position(2)

    wordsStateList = []

    if data['is_word_in_list'] == False:

        responseDictionary = {
            'correctGuess': False,
            'validGuess': False,
            'letterGuessTypeId': wordsStateList
        }

        return responseDictionary
    
    if data['is_correct'] == True:

        responseDictionary = {
            'correctGuess': True,
            'validGuess': True,
            'letterGuessTypeId': wordsStateList
        }

        return responseDictionary
    for char in data['character_info']:

        scoring = char['scoring']

        if scoring['in_word'] == False:
            tempDict = {'letterTypeId': 0}
        elif scoring['correct_idx'] == False and scoring['in_word'] == True:
            tempDict = {'letterTypeId': 1}
        elif scoring['correct_idx'] == True and scoring['in_word'] == True:
            tempDict = {'letterTypeId': 2}
        
        wordsStateList.append(tempDict)

    responseDictionary = {
        'correctGuess': data['is_correct'],
        'validGuess': data['is_word_in_list'],
        'letterGuessTypeId': wordsStateList
    }

    return responseDictionary

get_wordle_guess('whelp')