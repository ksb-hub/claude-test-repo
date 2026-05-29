# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Git 저장소의 로컬 및 원격 브랜치 구조를 한눈에 시각화하는 CLI 도구입니다.

## 실행 방법

```bash
python main.py
python main.py --path /path/to/repo
```

## 테스트 실행

```bash
python -m pytest tests/
python -m pytest tests/test_git_info.py::test_get_local_branches
```

## 프로젝트 구조

- `git_info.py` — git 명령어 실행 및 브랜치 정보 수집 로직
- `renderer.py` — 수집한 정보를 트리/표 형태로 출력하는 렌더링 로직
- `main.py` — CLI 진입점, 인자 파싱
- `tests/` — pytest 기반 단위 테스트

## 주요 설계 원칙

- 데이터 수집(`git_info.py`)과 출력(`renderer.py`)을 분리
- `subprocess`로 git 명령어를 실행하여 브랜치 정보를 파싱
- 외부 라이브러리 없이 표준 라이브러리만 사용
