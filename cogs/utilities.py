import random



class Queue():
    def __init__(self):
        
        # self.audio = {'title':'', 'url':'' ,'thumb':'', 'duration':''}
        self.original_queue = []
        self.queue = []
        self.current_audio = None

    # Set the current audio from the queue if available
    def set_current(self) -> None:
        if len(self.queue) >= 1:
            self.current_audio = self.queue[0] # The current audio will always be in index 0


    # Append audio to the queue as a dict
    def append_to_queue(self, audio_title:str, audio_url:str, audio_thumb:str, audio_duration=0) -> None:
        self.queue.append({'title':audio_title, 'url':audio_url, 'thumb':audio_thumb, 'duration':audio_duration}) # Append the element as a dict , added duration (in seconds)
        if len(self.queue) == 1:
            self.current_audio = self.queue[0] 

    # Set the next audio in the queue as the current one
    def next(self) -> None:
        if self.current_audio in self.queue:
            index = self.queue.index(self.current_audio)
            if (index == 0) and (len(self.queue) >= 1):
                self.queue.pop(0)
                self.current_audio = self.queue[0] # The next audio in line is now in index 0
        else: # If the current audio is not in the queue, so the queue is empty
            self.clear_queue()

    # Check if there is available element in the queue , if so return True, else return False (empty queue)
    def is_next_available(self) -> bool:
        if len(self.queue) > 1: # Changed from 0 to 1
            return True
        else:
            return False

    # Clear the queue
    def clear_queue(self) -> None:
        self.queue.clear()
        self.current_audio = None
    
    # Shuffle the queue
    def shuffle_queue(self) -> None:
        self.original_queue = self.queue
        queue_holder = self.queue[1:]
        random.shuffle(queue_holder)
        self.queue[1:] = queue_holder



# For multi-server option
class Session():
    def __init__(self, guild:str, channel:str, id=0):
        self.guild = guild
        self.channel = channel
        self.id = id
        self.q = Queue()