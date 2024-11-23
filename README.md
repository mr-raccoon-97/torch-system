# torch-system

The beta version of IA training system, created using domain driven design and an event driven architecture.

## Installation

Make sure you have a pytorch distribution installed. If you don't, go to the [official website](https://pytorch.org/) and follow the instructions.
    
Then, you can install the package using pip:

```bash
pip install torchsystem
```

Soon I will be adding the package to conda-forge when the package is more stable. Meanwhile you can install it with conda pip

```bash
conda install pip
pip install torchsystem
```


## Introduction

Machine learning systems are getting more and more complex, and the need for a more organized and structured way to build and maintain them is becoming more evident. Training a neural network requires to define a cluster of related objects that should be treated as a single unit, this defines an aggregate. The training process mutates the state of the aggregate producing data that should be stored  alongside the state of the aggregate in a transactional way. This establishes a clear bounded context that should be modeled using Domain Driven Design (DDD) principles.

The torch-system is a framework based on DDD and Event Driven Architecture (EDA) principles, using the [pybondi](https://github.com/mapache-software/py-bondi) library. It aims to provide a way to model complex machine models using aggregates and training flows using commands and events, and persist states and results using the repositories, the unit of work pattern and pub/sub.

It also provides out of the box tools for managing the training process, model compilation, centralized settings with enviroments variables using [pydantic-settings](https://github.com/pydantic/pydantic-settings), automatic parameter tracking using [mlregistry](https://github.com/mapache-software/ml-registry). 

## Getting Started

The main concepts of the torch-system are:

- **Aggregate**: A cluster of related objects, for example neural networks, optimizers, optimizers, etc.. Each aggregate has a unique identifier and a root that can publish domain events. For example, let's say we need to model a classifier, we can define an aggregate called `Classifier` that contains a neural network, an optimizer, a loss function, etc.

```python	
from typing import Any
from typing import Callable
from torch import Tensor
from torch import inference_mode
from torch.nn import Module
from torch.optim import Optimizer
from torchsystem import Aggregate
from torchsystem import Loader

class Classifier(Aggregate):
    def __init__(self, id: Any, model: Module, criterion: Module, optimizer: Optimizer):
        super().__init__(id)
        self.model = model
        self.criterion = criterion
        self.optimizer = optimizer

    def forward(self, input: Tensor):
        return self.model(input)

    def loss(self, output: Tensor, target: Tensor) -> Tensor:
        return self.criterion(output, target)

    def fit(self, loader: Loader, callback: Callable):
        for batch, (input, target) in enumerate(loader, start=1):
            self.optimizer.zero_grad()
            output = self(input)
            loss = self.loss(output, target)
            loss.backward()
            self.optimizer.step()
            callback(self.id, batch, loss.item(), output, target)

    @inference_mode()
    def evaluate(self, loader: Loader, callback: Callable):
        for batch, (input, target) in enumerate(loader, start=1):
            output = self(input)
            loss = self.loss(output, target)
            callback(self.id, batch, loss.item(), output, target)
```

- **Compilers**

In DDD, aggregates can be complex, with multiple fields or dependencies that require specific rules for instantiation. Factories manage this complexity by encapsulating the creation logic. In modern machine learning frameworks, model creating go hand in hand with model compilation, so it makes sense to encapsulate the compilation process as a factory alike object that produces compiled aggregates.

In torchsystem can create a compiled instance of the aggregate using the compiler class. Let's say we have a model named `MLP`.

```python

model = MLP(784, 128, 10, p=0.2, activation='relu')
criterion = CrossEntropyLoss()
optimizer = Adam(model.parameters(), lr=0.001)
compiler = Compiler(Classifier) # You pass a factory funcion or class to the compiler to create instances of the aggregate
                                # in this case, for simplicity we use the the constructor of the Classifier class as the factory
                                # But any factory you design can be used, in the case you need complex creation logic.
classifier = compiler.compile('1', model, criterion, optimizer)
```

- **Centralized settings**
 
But what about configuration? torch configurations can be very complex to manage, for example compilers have a set of parameters
that can be configured, but we are not seeing them in the example above. 

Every object in the torchsytem has a settings object instance initialized by default that can be used to configure them. For example, if you want to change the configuration of the compiler, you can do it like this:

```python

from torchsystem.settings import Settings, CompilerSettings

settings = Settings(compiler=CompilerSettings(fullgraph=True))
compiler = Compiler(Classifier, settings=settings)

```
But if you don't want to be messing around passing settings objects to every object you create, you can define enviroment variables
that will be readed automatically thanks to pydantic-settings. For example, you can define a `.env` file in the root of your project.

```bash
COMPILER_FULLGRAPH=True
COMPILER_RAISE_ON_ERROR=True 

LOADER_PIN_MEMORY=True
LOADER_PIN_MEMORY_DEVICE='cuda:0'
LOADER_NUM_WORKERS=4
```

And that's it, the settings will be readed automatically when you create the compiler object, without manually passing the settings object to every object you create. 

For more complex usage cases, you will need to create your own settings object to pass to your
defined aggregates. This can be done simply by inheriting from the `BaseSettings` class and defining the settings you need.

By default, the Settings object has an `AggregateSettings` object specifying the device for your aggregate. So you can refactor your aggregate to use it in it's training loop.

```python
from torchsystem.settings import Settings

class Classifier(Aggregate):
    def __init__(self, id: Any, model: Module, criterion: Module, optimizer: Optimizer, settings: Settings = None):
        super().__init__(id)
        self.model = model
        self.criterion = criterion
        self.optimizer = optimizer
        self.settings = settings or Settings()
    ...

    def fit(self, loader: Loader, callback: Callable):
        device = self.settings.aggregate.device
        for batch, (input, target) in enumerate(loader, start=1):
            input, target = input.to(device), target.to(device)
            ...         
```
And in your `.env` file you can define the device for your aggregate.

```bash
AGGREGATE_DEVICE='cuda:0'
```


- **Loaders**

Now let's train the classifier using loaders. The `Loaders` are a way to encapsulate the data loading process. You can use raw
data loaders from pytorch if you want, just like you were doing:

```python
from torch.utils.data import DataLoader

loaders = [
    ('train', DataLoader(Digits(train=True), batch_size=32, shuffle=True)),
    ('eval', DataLoader(Digits(train=False), batch_size=32, shuffle=False))
]

```

But if you decide to use the `Loaders` class will automatically track the parameters of you dataloaders using
the `mlregistry` library.  

```python

from torchsystem import Loaders

loaders = Loaders() #This has a default Settings object initialized reading .env files.
loaders.add('train', Digits(train=True), batch_size=32, shuffle=True) 

settings = Settings(loaders=LoadersSettings(num_of_workers=2)) # If you need something more fine grained.
loaders.add('eval', Digits(train=False), batch_size=32, shuffle=False, settings=settings) #Settings can also be passed to each loader
                                                                                          #individually.
```

- **Sessions (Unit of work)**

Finally, you can train the classifier using predefined training and evaluation loops in the commands (or something defined by you in
a command handler). Let's start a training session.

```python
from torchsystem import Session
from torchsystem.commands import Iterate # Iterates over the loaders class
from torchsystem.commands import Train, Evaluate # If you want a more fine grained control over the training process
                                                 # you can use the Train and Evaluate commands that will accept a single
                                                 # and configure the aggregate accordingly in training or inference mode.

with Session() as session:
    session.add(classifier)
    for epoch in range(1, 10):
        session.execute(Iterate(classifier, loaders)) #Will fit the aggregate for training loaders and evaluate them otherwise.
```

The `Session` class is a context manager that will automatically start and stop a pub/sub system, commit or rollback it in case of errors,
store or restore the state of the aggregates given a defined repository, handle the events produced by the aggregates during the execution
of the commands using a messagebus and handlers you define, and will not be restricted to the default command handlers, you can also use your own with handlers you define. 


- **Callbacks**

"But what about metrics? I'm just seeing the loss being logged in my terminal". That's what callbacks are for. By default, torchsystem tracks the loss of your model, but this can be extended to any metric you want with callbacks. There are some predefined callbacks in the `torchsystem.callbacks`.

```python
from torchsystem.callbacks import Callbacks # This will let you use several callbacks at once
from torchsystem.callbacks.average import Loss, Accuracy # You can use predefined callbacks for loss and accuracy averages

callbacks = Callbacks([Loss(), Accuracy()])
...
    for epoch in range(1, 10):
        session.execute(Iterate(classifier, loaders, callbacks))
```

- **Message Publishers**

You can publish the metrics produced in the callbacks using a publisher. The publisher will publish the metrics in a topic, and you can subscribe to that topic to get the metrics. A publisher will be automatically created by the session and you can add subscribers fron there, but you can also pass your own publisher to the session, as you can with a repository or even a messagebus.

```python
from torchsystem import Publisher

publisher = Publisher()
publisher.subscribe('metrics', lambda metric: print(metric)) # Use the tracking library you want to store the metrics like tensorboard

repository = MyRepository() # Your own repository class with store, and restore methods implemented for your aggregates

callbacks.bind(publisher)

with Session(repository, publisher) as session:
    session.add(classifier)
    for epoch in range(1, 10):
        session.execute(Iterate(classifier, loaders, callbacks))
        if epoch % 4 == 0:
            session.commit() # Everything will be commited or rolledback if session.rollback() as a single unit,
                             # including metrics published by the publisher.
        if epoch % 5 == 0:
            raise Exception('Something went wrong') # Everything will be rolled back to the last commit point.
```
- **Events**

There are even more stuff you can do with the torchsystem. Let's say you don't want to use repositories but persist your aggregates with events instead. Let's see an example of how you can do this using also the `mlregistry` library for metadata tracking.

```python

from mlregistry import get_metadata #This is also avaliable under the torchsystem.storage namespace
from torchsystem.storage import Models, Criterions, Optimizers
from torchsystem.events import Added, RolledBack, Saved
from torchsystem.events import Iterated # Use this if you want to persist data of for example, datasets
                                        # that you used to train-evaluate an object.

Models.register(MLP)
Criterions.register(CrossEntropyLoss)
Optimizers.register(Adam)
# If you don't need to track the metada of the model, you can skip the register step and
# just store the weights using the Weight[T] class from the torchsystem.weights module.

model = MLP(784, 128, 10, p=0.2, activation='relu')
criterion = CrossEntropyLoss()
optimizer = Adam(model.parameters(), lr=0.001)

def persist_model(event: Added[Classifier]):
    metadata = get_metadata(event.aggregate.model) 
    print(f'Persisting model {metadata.name} with parameters {metadata.parameters}')
    # {'in_features': 784, 'out_features': 128, 'p': 0.2, 'activation': 'relu'} # Do whatever you want with this. Print it, store it in a database, etc.
    # This is recorded thanks to the mlregistry library embedded in the Models class.
    models = Models()
    models.store(event.aggregate.model) 
    ... # You are free to do whatever you want with the model. I suggest just doing one thing per event handler.
    # And add several event handlers to the same event if you need to do several things with the same event.

def persist_optimizer(event: Added[Classifier], optimizers: Optimizers):
    metadata = get_metadata(event.aggregate.criterion) 
    criterions.store(event.aggregate.criterion)
    ...

def print_datasets(event: Iterated[Classifier]):
    for phase, loader in event.loaders:
        metadata = get_metadata(loader.dataset)
        ...
        #Do anything you want here.

Session.add_event_handler(Added, persist_model)
Session.add_event_handler(Added, lambda event: persist_optimizer(event, Optimizers()))
# This is just a way to pass dependencies to the event handler. You can also do it with functools.partial. 

with Session() as session:
    session.add(classifier) # Will trigger the Added event
    for epoch in range(1, 10):
        session.execute(Iterate(classifier, loaders, callbacks))
        session.commit() # Will trigger the Saved event
```

A messagebus can be used to inject all the event and command handlers into the session. You can use it with decorators in your service layers.

```python

from torchsystem import Messagebus
from torchsystem.events import Added, RolledBack, Iterated

messagebus = Messagebus()

@messagebus.subscribe(Added, Commited)
def bring_current_epoch(event: Added[Classifier] | RolledBack[Classifier]):
    '''
    When you add a classifier to the session or if the session is rolled back
    you need to bring the current epoch of the classifier to the current state.
    '''
    event.aggregate.epoch = get_current_epoch(event.aggregate.id) # or something like that.


with Session(messagebus=messagebus) as session:
    session.add(classifier) # Will trigger the Added event
    for epoch in range(1, 10):
        session.execute(Iterate(classifier, loaders, callbacks))
        session.commit() # Will trigger the Saved event
```

In the future I will see if I can add a dependency injection mecanism like the one in the `fastapi` library to the torchsystem.

And that's it, you have a complete training system using DDD and EDA principles. You can define your own aggregates, commands, events, repositories, and handlers to create a complex training system that can be easily maintained and extended. There are event more stuff you can do with the torchsystem. 

This is a very first working version of the torchsystem. The idea is to deploy real time machine learning systems not only for inference, but also for training in servers using REST apis. A lot of wild ideas come to my mind when I think about the possibilities of this system, like deploy distributed multi-model agents that can train them selves, models that raise events containing embeddings similar to a brain reacting to something, etc.

Any feedback or contribution is welcome.