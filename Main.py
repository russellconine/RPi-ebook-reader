
# project tomcat

import vlc
import os
import re
import RPi.GPIO as GPIO
import time

global playing
playing = False

global player


def readDirectory():
    '''
        Method reads directory on lexar flash drive that contains book files. Creates list of book titles,
        and number of files per title. (each book is saved as multiple files)
    '''
    dirList = sorted(os.listdir('/media/pi/Lexar/'))
    bookList = []
    fileCount = []
    counter = 0
    first = True
    for name in dirList:
        audioFile = re.findall('.+.mp3',name)
        if audioFile:
            bookName = audioFile[0][:-11]
            if first:
                bookList.append(bookName)
                first = False
                counter = 1
            else:
                if bookList[-1] != bookName:
                    bookList.append(bookName)
                    fileCount.append(counter)
                    counter = 1
                else:
                    counter = counter + 1

    fileCount.append(counter)
    
    return bookList, fileCount


def createMetaFile(bookList,fileCount):
    """
        Method creates meta file. Meta file stores information on which book is currently playing, 
        and the current file number and progress for each book.
    """
    currentBook = 0
    try:        # code for if meta file already exists
        f = open('meta.txt','r')
        metaContents = f.readlines()
        f.close()
        f=open('meta.txt','w')
        i = 0
        for line in metaContents:
            newLine = re.findall('CURRENTBOOK' + '.+',line)
            if newLine:
                f.write(newLine[0][11:]+'\n')
                currentBook = i
            else:
                f.write(line)
            i = i + 1
        f.close()
    except:     # code for creating meta.txt if doesn't exist
        f = open('meta.txt', 'w')
        chapter= 1
        fractional = 0
        for name in bookList:
            f.write(name + ',')
            f.write(str(chapter)+ ',')
            f.write(str(fractional) + '\n')

        f.close()
  
    return (currentBook)
        

def updateMetaFile(currentBookTitle,fractional,buttonFn):
    """
        Method updates meta file each time fast forward, rwd, or poweroff button is pressed. 
    """
    f = open('meta.txt','r')
    metaContents = f.readlines()
    f.close()
    chapterVar= 0
    powerDown = False
    f=open('meta.txt','w')
    if buttonFn == 'rewind':
        chapterVar = -1
    elif buttonFn == 'fwd':
        chapterVar= 1
    elif buttonFn == True:
        powerDown = True
    for line in metaContents:
        newLine= re.findall(currentBookTitle + '.+', line)
        chapter = int(re.findall(',\d+,',line)[0][1:-1])
        if chapter == 1 and chapterVar == -1:
            chapter = 2
            fractional = 0
        if newLine and not powerDown:
            f.write(currentBookTitle+','+str(chapter+chapterVar)+','+str(fractional) +'\n')
        elif newLine and powerDown:
            f.write('CURRENTBOOK'+currentBookTitle+','+str(chapter+chapterVar)+','+str(fractional)+'\n')
        else:
            f.write(line)
    f.close()

def initializeGPIO():
    """
        Initializes Raspberry Pi's GPIO board.
    """
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(36,GPIO.IN,pull_up_down=GPIO.PUD_DOWN) # play/pause button
    GPIO.setup(22,GPIO.IN,pull_up_down=GPIO.PUD_DOWN) # sort down to next book
    GPIO.setup(35,GPIO.IN,pull_up_down=GPIO.PUD_DOWN) # sort up to previous book
    GPIO.setup(12,GPIO.IN,pull_up_down=GPIO.PUD_DOWN) # Power off
    GPIO.setup(18,GPIO.IN,pull_up_down=GPIO.PUD_DOWN) # Fast forward
    GPIO.setup(15,GPIO.IN,pull_up_down=GPIO.PUD_DOWN) # Rewind
    GPIO.setup(40,GPIO.OUT)                           # lightup when booted


def chapterSanitize(chapter):
    '''
        Removes 0 from chapter strings less than 10. Ex chapter 01 becomes chapter 1, 02 -> 2, etc.
    '''
    if int(chapter) < 10:
        outChapter = '0' + str(chapter)
    else:
        outChapter = str(chapter)
    return outChapter

def readMP3(currentBookTitle,typeVar):
    '''
        Reads selected book out loud.
    '''
    f = open('meta.txt','r')
    metaContents = f.readlines()
    f.close()
    bookTicker = 1
    i = 1
    for line in metaContents:
        newLine= re.findall(currentBookTitle + '.+', line)
        if newLine:
            locationData = re.findall(',\d+\.?\d*',newLine[0])
            bookTicker = str(i)
        i = i+1
    chapter = locationData[0][1:]
    fractional = float(locationData[1][1:])
    chapterString = chapterSanitize(chapter)
    audioFile = '/media/pi/Lexar/' + currentBookTitle + '-Part' +chapterString+'.mp3'
    global player
    global playing
    if typeVar == 'ffrwd':
        pass
    else:
        readBookNumAndTitle(bookTicker,currentBookTitle)
    player=vlc.MediaPlayer(audioFile)
    
    player.play()
    player.set_position(fractional)

    playing = True

def readBookNumAndTitle(number,title):
    """
        Uses espeak program to read out loud the number and title of book.
    """
    systemString = "espeak 'book {}. {}.' -v en-us -s 175 -g 10".format(number,title)
    os.system(systemString)

def rewind(fractional,player,currentBookTitle):
    """
        Method when rewind button is pressed. Each chapter is divided into "fractionals." If fractional value
        is 0.5, then that chapter is 50% finished. If fractional is more than .01, player will rewind within
        chapter. If fractional is less than .01, player will go to end (.99) of previous chapter.
    """
    if fractional > .01:
        fractional = fractional -.01
        updateMetaFile(currentBookTitle,fractional,'other')
        closeAndPlay(player,currentBookTitle,'ffrwd')
    else:
        fractional = .99
        updateMetaFile(currentBookTitle,fractional,'rewind')

def fastForward(fractional,player,currentBookTitle):
    """
        Method when fast forward button is pressed. Each chapter is divided into "fractionals." Behaves 
        similar to rewind, except that if fast-forwarded in final .01 of chapter, player skips to 0 of next
        chapter.
    """
    if fractional < .99:
        fractional = fractional +.01
        updateMetaFile(currentBookTitle,fractional,'other')
        closeAndPlay(player,currentBookTitle,'ffrwd')
    else:
        fractional = 0
        updateMetaFile(currentBookTitle,fractional,'fwd')
        closeAndPlay(player,currentBookTitle,'ffrwd')
        

def sanitize(pinNum):
    """
        Method prevents multiple button presses. Each time button is pressed, sanitizer pauses for .1 sec.
        IE input of 1111101010111001000010000 will be sanitized to 1.
    """
    while GPIO.input(pinNum):
        time.sleep(.1)
    
def closePlayer(player):
    """
        Stops player
    """
    player.stop()

def closeAndPlay(player,currentBookTitle,typeVar):
    """
        Calls method to stop player. Then starts playing. This method stops old player and starts new one.
    """
    closePlayer(player)
    readMP3(currentBookTitle,typeVar)

def powerOff(currentBookTitle,fractional):
    """
        stops player, updates meta file for next time you turn on player. cleans up GPIO board
    """
    global player
    player.stop()
    updateMetaFile(currentBookTitle,fractional,True)
    GPIO.cleanup()

    
def mainloop():
    """
        Infinite main loop runs until Raspberry Pi is powered off by pressing power button. This method
        waits for input from each button, then calls the appropriate function based on button pressed.
    """
    global playing
    global player
    currentBook = 0
    initial = True
    
    [bookList, fileCount] = readDirectory()
    currentBook = createMetaFile(bookList,fileCount)
    initializeGPIO()
    GPIO.output(40,1)

    
    while True:
        if initial and GPIO.input(36):
            try:
                readMP3(bookList[currentBook],'none')
            except:
                GPIO.output(40,0)
            initial = False
        elif initial and GPIO.input(35):
            if currentBook <= len(fileCount)-2:
                currentBook=currentBook+1
            else:
                currentBook=0
            sanitize(35)
        elif initial and GPIO.input(22):
            if currentBook == 0:
                currentBook=len(fileCount)-1
            else:
                currentBook=currentBook-1
            sanitize(22)
        elif GPIO.input(36) and playing and not initial:
            currentLocation = player.get_position()
            player.pause()
            updateMetaFile(bookList[currentBook],currentLocation,False)
            playing = False
            sanitize(36)

        elif GPIO.input(36) and not playing and not initial:
            player.set_position(currentLocation)
            player.play()
            playing= True
            sanitize(36)

        elif not initial and GPIO.input(35):
            currentLocation = player.get_position()
            updateMetaFile(bookList[currentBook], currentLocation,False) 
            if currentBook <= len(fileCount)-2:
                currentBook=currentBook+1
            else:
                currentBook=0   
            closeAndPlay(player,bookList[currentBook],'none')
            sanitize(35)

        elif not initial and GPIO.input(22):
            currentLocation = player.get_position()
            updateMetaFile(bookList[currentBook], currentLocation,False) 
            if currentBook == 0:
                currentBook=len(fileCount)-1
            else:
                currentBook=currentBook-1
            closeAndPlay(player,bookList[currentBook],'none')
            sanitize(22)

        elif not initial and GPIO.input(15):
            rewind(player.get_position(),player,bookList[currentBook])
            sanitize(15)

        elif not initial and GPIO.input(18):
            fastForward(player.get_position(),player,bookList[currentBook])
            sanitize(18)

        elif GPIO.input(12) and initial:
            GPIO.cleanup()
            os.system('poweroff')

        elif GPIO.input(12) and not initial:
            powerOff(bookList[currentBook],player.get_position())
            os.system('poweroff')

mainloop()
