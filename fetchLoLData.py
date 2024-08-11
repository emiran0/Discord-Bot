import requests
import numpy as np
import json
import urllib.parse
from collections import Counter


async def get_lol_info(summoner_name, summoner_tag):
    
    
    url_summoner_name = urllib.parse.quote(summoner_name)
    url_summoner_tag = urllib.parse.quote(summoner_tag)
    
    account_url = f'https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{url_summoner_name}/{url_summoner_tag}?api_key=RGAPI-4a128b28-4e48-4d8a-9efd-7edc13579d3f'

    response = requests.get(account_url)
    user_body = response.json()

    user_puuid = user_body['puuid']
    matchHistoryLength = 20

    url = f'https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{user_puuid}/ids?start=0&count={matchHistoryLength}&api_key=RGAPI-4a128b28-4e48-4d8a-9efd-7edc13579d3f'

    response = requests.get(url)

    matchIDList = response.json()

    matchHistory = []


    for match in matchIDList:
        match_url = f'https://europe.api.riotgames.com/lol/match/v5/matches/{match}?api_key=RGAPI-4a128b28-4e48-4d8a-9efd-7edc13579d3f'
        response = requests.get(match_url)
        response = response.json()
        player_list = response['info']['participants']
        for player in player_list:
            if player['puuid'] == user_puuid:
                tempDict = {}
                tempDict['matchId'] = response['metadata']['matchId']
                tempDict['kills'] = player['kills']
                tempDict['deaths'] = player['deaths']
                tempDict['assists'] = player['assists']
                tempDict['win'] = player['win']
                tempDict['kdaScore'] = (player['kills'] + player['assists']) / (1 if player['deaths'] == 0 else player['deaths'])
                tempDict['champion'] = player['championName']
                tempDict['minionsKilled'] = player['totalMinionsKilled'] + player['neutralMinionsKilled']
                tempDict['visionScore'] = player['visionScore']
                tempDict['damageDealt'] = player['totalDamageDealtToChampions']
                matchHistory.append(tempDict)


    # with open('data.json', 'w') as f:
    #     json.dump(full_body, f)

    winCount = 0
    winRate = 0
    kdaOverAll = 0
    minonsKilledAverage = 0
    visionScoreAverage = 0
    averageDamageDealt = 0
    championsPlayed = []
    matchCount = 20

    for match in matchHistory:

        if match['minionsKilled'] > 500:
            matchCount -= 1
        else:
            minonsKilledAverage += match['minionsKilled']

            championsPlayed.append(match['champion'])
        
            if match['win']:
                winCount += 1

            kdaOverAll += match['kdaScore']
            
            visionScoreAverage += match['visionScore']

            averageDamageDealt += match['damageDealt']

        

    championsPlayed = Counter(championsPlayed)
    mostlyPlayedChampion = championsPlayed.most_common(1)[0][0]
        
    winRate = round((winCount / matchCount) * 100, 2)
    kdaOverAll = round(kdaOverAll / matchCount, 2)
    minonsKilledAverage = round(minonsKilledAverage / matchCount, 2)
    visionScoreAverage = round(visionScoreAverage / matchCount, 2)
    averageDamageDealt = round(averageDamageDealt / matchCount, 2)

    print(winRate)
    print(kdaOverAll)

    statsDict = {'winRate': winRate, 'kdaOverAll': kdaOverAll, 'minionsKilledAverage': minonsKilledAverage, 'visionScoreAverage': visionScoreAverage, 'mostlyPlayedChampion': mostlyPlayedChampion, 'averageDamageDealt': averageDamageDealt}

    return statsDict

