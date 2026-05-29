from calculator import add, subtract, multiply, divide

def get_number(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("숫자를 입력해주세요.")

def get_operator():
    operators = {'+', '-', '*', '/'}
    while True:
        op = input("연산자를 입력하세요 (+, -, *, /): ").strip()
        if op in operators:
            return op
        print("올바른 연산자를 입력해주세요.")

def calculate(a, op, b):
    if op == '+':
        return add(a, b)
    elif op == '-':
        return subtract(a, b)
    elif op == '*':
        return multiply(a, b)
    elif op == '/':
        return divide(a, b)

def main():
    print("=== 계산기 ===")
    while True:
        a = get_number("첫 번째 숫자: ")
        op = get_operator()
        b = get_number("두 번째 숫자: ")

        try:
            result = calculate(a, op, b)
            print(f"결과: {a} {op} {b} = {result}")
        except ValueError as e:
            print(f"오류: {e}")

        again = input("계속하시겠습니까? (y/n): ").strip().lower()
        if again != 'y':
            print("종료합니다.")
            break

if __name__ == "__main__":
    main()
