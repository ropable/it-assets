from sockpuppet.reflex import Reflex


class AddressbookReflex(Reflex):
    def increment(self):
        self.count = (
            int(self.element.dataset['count']) +
            int(self.element.dataset['step'])
        )
