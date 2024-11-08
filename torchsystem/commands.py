from typing import Sequence
from dataclasses import dataclass
from pybondi import Command
from pybondi.callbacks import Callback
from torchsystem.aggregate import Aggregate
from torchsystem.aggregate import Loader

@dataclass
class Train(Command):
    '''
    The Train command is used to train the aggregate using the sequence of loaders provided. 
    It bumps the epoch after training the aggregate.
    '''
    aggregate: Aggregate
    loaders: Sequence[Loader]
    callback: Callback
    
    def execute(self):
        self.aggregate.phase = 'train'
        self.callback.set('phase', self.aggregate.phase)
        self.callback.set('epoch', self.aggregate.epoch)
        for loader in self.loaders:
            self.aggregate.fit(loader, self.callback)
        self.aggregate.epoch += 1

@dataclass
class Evaluate(Command):
    '''
    The Evaluate command is used to evaluate the aggregate using the sequence of loaders provided. 
    The aggregate is put on evaluation mode. It does not bump the epoch since it is not training the aggregate. 
    '''
    aggregate: Aggregate
    loaders: Sequence[Loader]
    callback: Callback
    
    def execute(self):
        self.aggregate.phase = 'evaluation'
        self.callback.set('phase', self.aggregate.phase)
        self.callback.set('epoch', self.aggregate.epoch)
        for loader in self.loaders:
            self.aggregate.evaluate(loader, self.callback)

@dataclass
class Iterate(Command):
    '''
    The Iterate command is used to iterate over the sequence of loaders provided.
    It determines the phase of the aggregate and calls the fit or evaluate method accordingly.
    After iterating over the loaders, it bumps the epoch.
    '''

    aggregate: Aggregate
    loaders: Sequence[tuple[str, Loader]]
    callback: Callback
    
    def execute(self):
        self.callback.set('epoch', self.aggregate.epoch)
        for phase, loader in self.loaders:
            self.aggregate.phase = phase
            self.callback.set('phase', self.aggregate.phase )
            self.aggregate.iterate(loader, self.callback)
        self.aggregate.epoch += 1