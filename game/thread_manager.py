from threading import Thread


class ThreadManager:
    def __init__(self):
        self.threadpool = []

    def add_thread(self, thread: Thread):
        self.threadpool.append(thread)

    def remove_thread(self, thread: Thread):
        try:
            self.threadpool.remove(thread)
        except ValueError:
            return
        # if thread.is_alive:
        #     thread.stop()

    def shutdown(self):
        ...
        # for thread in self.threadpool:
        #     if thread and thread.is_alive:
        #         thread.stop()
