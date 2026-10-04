# MAYA AI Model Stack

MAYA does not rely solely on an external proprietary API. She employs a modular model architecture designed for local inference and custom fine-tuning.

## Model Hierarchy

1. **Deterministic Intent Classifier**:
   - Sub-millisecond rule-guided classifier for unambiguous tool calling and safety checking.
   - Operates 100% offline with zero latency.

2. **Local Fine-Tuned Model (`MayaFineTunedModel`)**:
   - Represents the custom MAYA personality, reasoning, and tool-calling adapter.
   - Built on open-weight base models such as Llama-3-8B-Instruct or Qwen-2.5-7B.

3. **Local Endpoint Provider (`LocalModelProvider`)**:
   - Connects to locally running inference engines such as Ollama, LM Studio, or llama.cpp (`http://127.0.0.1:11434`).

4. **Optional Cloud Provider (`OptionalCloudModelProvider`)**:
   - Configurable fallback for heavy reasoning tasks if offline-first mode is disabled by the user.

## Interfaces
All providers implement the `ModelProvider` abstract base class:
```python
class ModelProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
```
