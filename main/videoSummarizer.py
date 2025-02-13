# Imports
import argparse
import os
import pysrt
import re
import subprocess
import sys
import math
import pytube
import six
from moviepy import VideoFileClip, TextClip, ImageClip, concatenate_videoclips

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

from sumy.summarizers.luhn import LuhnSummarizer
from sumy.summarizers.edmundson import EdmundsonSummarizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer
import nltk
nltk.download('punkt')

SUMMARIZERS = {
    'LU': LuhnSummarizer,
    'ED': EdmundsonSummarizer,
    'LS': LsaSummarizer,
    'TR': TextRankSummarizer,
    'LR': LexRankSummarizer
}

# Function to concatenate the video to obtain the summary
def create_summary(filename, regions):
    subclips = []
    # obtain video
    input_video = VideoFileClip(filename)
    # Scan through video and store the subclips in an array
    last_end = 0
    for (start, end) in regions:
        subclip = input_video.subclip(start, end)
        subclips.append(subclip)
        last_end = end

    # return the concatenated videoclip to the
    return concatenate_videoclips(subclips)

# Function to find the range of the subtitles in seconds
def srt_item_to_range(item):
    start_s = item.start.hours*60*60 + item.start.minutes*60 + item.start.seconds + item.start.milliseconds/1000.
    end_s = item.end.hours*60*60 + item.end.minutes*60 + item.end.seconds + item.end.milliseconds/1000.
    return start_s, end_s

# Function to convert srt file to document in such a way that each sentence starts with '(sentence no)'
# It also removes all the unwanted stray elements in the srt file
def srt_to_doc(srt_file):
    text = ''
    for index, item in enumerate(srt_file):
        ##print(item.text)
        if item.text.startswith("["): continue
        text += "(%d) " % index
        text += item.text.replace("\n", "").strip("...").replace(".", "").replace("?", "").replace("!", "")
        text += ". "
    return text

def total_duration_of_regions(regions):
    totalT=0
    for i in range(len(regions)):
        if(((regions[i])[1]-(regions[i])[0]) > 0):
            totalT=totalT+(regions[i])[1]-(regions[i])[0]
    return totalT
    #return sum(list(map(lambda rangeValue : rangeValue[1]-rangeValue[0] , regions)))

def summarize(srt_file, summarizer, n_sentences, language, bonusWords, stigmaWords):
    # Converting the srt file to a plain text document and passing in to Sumy library(The text summarization library) functions.
    ##print(srt_to_doc(srt_file))
    parser = PlaintextParser.from_string(srt_to_doc(srt_file), Tokenizer(language))

    if(summarizer == 'ED'):
        summarizer = EdmundsonSummarizer()

        with open(bonusWords,"r+") as f:
            bonus_wordsList = f.readlines()
            bonus_wordsList = [x.strip() for x in bonus_wordsList]
            f.close()
        with open(stigmaWords,"r+") as f:
            stigma_wordsList = f.readlines()
            stigma_wordsList = [x.strip() for x in stigma_wordsList]
            f.close()

        summarizer.bonus_words = (bonus_wordsList)
        summarizer.stigma_words = (stigma_wordsList)
        summarizer.null_words = get_stop_words(language)
    else:
        stemmer = Stemmer(language)
        summarizer = SUMMARIZERS[summarizer](stemmer)
        summarizer.stop_words = get_stop_words(language)

    ret = []
    summarizedSubtitles = []
    # Now the the document passed is summarized and we can access the filtered sentences along with the no of sentence
    # for sentence in parser.document:
    #     print("sentence ",sentence)
    # print("cod ",srt_file)
    # for ob in srt_file:
    #         sent=srt_to_doc([ob])
    #         print("sent ",sent[4:])

    for sentence in summarizer(parser.document, n_sentences):
        # Index of the sentence
        # print("sentence ",sentence)
        index = int(re.findall("\(([0-9]+)\)", str(sentence))[0])
        # Using the index we determine the subtitle to be selected
        item = srt_file[index]
        # print("item ",item)
        summarizedSubtitles.append(item)

        # add the selected subtitle to the result array
        ret.append(srt_item_to_range(item))

    return ret,summarizedSubtitles

def find_summary_regions(srt_filename, summarizer, duration, language ,bonusWords,stigmaWords,videonamepart):
    srt_file = pysrt.open(srt_filename)
    # Find the average amount of time required for each subtitle to be showned

    clipList = list(map(srt_item_to_range,srt_file))

    avg_subtitle_duration = total_duration_of_regions(clipList)/len(srt_file)

    # Find the no of sentences that will be required in the summary video
    n_sentences = duration / avg_subtitle_duration
    print("nsentance : "+str(n_sentences))

    # get the summarize video's subtitle array
    [summary,summarizedSubtitles] = summarize(srt_file, summarizer, n_sentences, language, bonusWords, stigmaWords)
    # Check whether the total duration is less than the duration required for the video
    total_time = total_duration_of_regions(summary)
    print("total_time : "+str(total_time))
    try_higher = total_time < duration
    prev_total_time = -1
    # If the duration which we got is higher than required
    if try_higher:
        # Then until the resultant duration is higher than the required duration run a loop in which the no of sentence is increased by 1
        while total_time < duration:
            if(prev_total_time==total_time):
                print("1 : Maximum summarization time reached")
                break
            print("1 : total_time : duration "+str(total_time)+" "+str(duration))
            n_sentences += 1
            [summary,summarizedSubtitles] = summarize(srt_file, summarizer, n_sentences, language, bonusWords, stigmaWords)
            prev_total_time=total_time
            total_time = total_duration_of_regions(summary)
    else:
        # Else if  the duration which we got is lesser than required
        # Then until the resultant duration is lesser than the required duration run a loop in which the no of sentence is increased by 1
        while total_time > duration:
            if(n_sentences<=2):
                print("2 : Minimum summarization time reached")
                break
            print("2 : total_time : duration "+str(total_time)+str(duration))
            n_sentences -= 1
            [summary,summarizedSubtitles] = summarize(srt_file, summarizer, n_sentences, language, bonusWords, stigmaWords)
            total_time = total_duration_of_regions(summary)

    print("************ THis is summary array *********")
    print(summary)
    print("**********************************")

    print("************************THis is summarizedSubtitles array *******************")
    print(summarizedSubtitles)
    print("**********************************************************")
    # Find the duration of each subtitle and add it to the ending time of the previous subtitle
    subs=[]
    starting=0
    sub_rip_file = pysrt.SubRipFile()
    for index,item in enumerate(summarizedSubtitles):
        newSubitem=pysrt.SubRipItem()
        newSubitem.index=index
        newSubitem.text=item.text
        # First find duration
        duration=summary[index][1]-summary[index][0]
        # Then find the ending time
        ending=starting+duration
        newSubitem.start.seconds=starting
        newSubitem.end.seconds=ending
        sub_rip_file.append(newSubitem)
        # subs.append((index,starting,ending,item.text))
        starting=ending

    print(sub_rip_file)

    # print(subs)


    path = videonamepart+".srt"
    with open(path,"w+") as sf:
        for i in range(0,len(sub_rip_file)):
            sf.write(str(sub_rip_file[i]))
            sf.write("\n")
    sf.close()

    #test file for finding emotions
    # path = "./media/documents/summarizedSubtitleText.txt"
    # with open(path,"w+") as stf:
    #     for i in range(0,len(summarizedSubtitles)):
    #         stf.write(str(summarizedSubtitles[i].text))
    #         stf.write("\n")
    # stf.close()

    # return the resulant summarized subtitle array
    return summary


def summarizeVideo(videoName,subtitleName,summType,summTime,bonusWords,stigmaWords):

    # print("Enter the video filename")
    video=videoName

    # print("Enter the subtitle name ")
    subtitle=subtitleName

    # print("Enter summarizer name ")
    summarizerName=summType
    duration=int(summTime)
    language='english'
    base, ext = os.path.splitext(video)
    print("base : "+str(base))
    videonamepart = "{0}_".format(base)
    commonName = videonamepart +str(summarizerName)+"_summarized"
    videoUrl=commonName+".mp4"

    # print("dst : "+str(dst))
    regions = find_summary_regions(subtitle,
                                   summarizer=summarizerName,
                                   duration=duration,
                                   language=language,
                                   bonusWords=bonusWords,
                                   stigmaWords=stigmaWords,
                                   videonamepart=commonName
                                   )
    print((regions[-1])[1])
    if((regions[-1])[1]==0):
        regions = regions[:-1]
    print("regions : ")
    print(regions)

    summary = create_summary(video,regions)
    # Converting to video
    summary.to_videofile(
        videoUrl,
        codec="libx264",
        temp_audiofile="temp.m4a",
        remove_temp=True,
        audio_codec="aac",
    )
    return commonName
