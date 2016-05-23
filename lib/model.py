class AttributeDict(dict): 
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

class Program(AttributeDict):
    def __init__(self, *args, **kwargs):
        super(Program, self).__init__(*args, **kwargs)
