# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Python으로 만드는 간단한 계산기 프로그램입니다.

## 실행 방법

```bash
python calculator.py
```

## 테스트 실행

```bash
python -m pytest tests/
# 단일 테스트 실행
python -m pytest tests/test_calculator.py::test_add
```

## 프로젝트 구조

- `calculator.py` — 핵심 계산 로직 (사칙연산 함수)
- `main.py` — 사용자 입력 처리 및 CLI 인터페이스
- `tests/` — pytest 기반 단위 테스트

## 주요 설계 원칙

- 계산 로직(`calculator.py`)과 UI 로직(`main.py`)을 분리하여 유지
- 각 연산은 독립적인 함수로 구현 (add, subtract, multiply, divide)
- 0으로 나누기 등 예외 상황은 예외(Exception)를 발생시켜 처리
