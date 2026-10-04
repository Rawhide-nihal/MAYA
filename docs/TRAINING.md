# MAYA Model Fine-Tuning Guide

This guide describes how to train a custom MAYA adapter using Supervised Fine-Tuning (SFT) and Low-Rank Adaptation (LoRA / QLoRA).

## 1. Dataset Format
MAYA training samples are structured in JSONL:
```json
{
  "instruction": "Open VS Code and check my project.",
  "input": "",
  "output": "Sure! I'll open VS Code, scan your project, and check for any errors. Give me a moment...",
  "intent": "DEVELOPMENT_ACTION",
  "tools": ["open_application", "inspect_project"]
}
```
The active dataset is located at:
`training/datasets/maya_sft_dataset.jsonl`

## 2. Fine-Tuning Execution
The training script is located at `training/finetuning/train_lora.py`.

To run fine-tuning:
```powershell
pip install transformers peft trl bitsandbytes datasets accelerate
python training/finetuning/train_lora.py
```

## 3. Evaluation Suite
Verify that the model refuses unauthorized actions, selects appropriate tools, and retains personality traits:
```powershell
python training/evaluation/eval_suite.py
```
Outputs intent match score, tool argument accuracy, and critical refusal validation.
