from threading import Thread

from listeners import on_tick_listener_manager


class SPThread(Thread):
    def start(self):
        on_tick_listener_manager.register_listener(self._tick)

        super().start()

    def stop(self):
        on_tick_listener_manager.unregister_listener(self._tick)

    def _tick(self):
        pass
