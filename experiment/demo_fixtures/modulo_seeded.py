import math


def calculate(left: float, operator: str, right: float) -> float:
    """Calculate one operation, rejecting invalid operators and zero divisors."""
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "%":
        if right == 0:
            raise ValueError("Cannot take modulo by zero.")
        return math.fmod(left, right)
    if operator == "/":
        if right == 0:
            raise ValueError("Cannot divide by zero.")
        return left / right
    raise ValueError("Choose +, -, *, or /. You can also choose %.")


def read_number(prompt: str) -> float:
    """Read a finite number, allowing the user to retry invalid input."""
    while True:
        try:
            number = float(input(prompt))
            if math.isfinite(number):
                return number
        except ValueError:
            pass
        print("Please enter a finite number.")


def main() -> None:
    print("Calculator: +, -, *, / (enter q to quit)")
    try:
        while True:
            operator = input("Operation: ").strip().lower()
            if operator in {"q", "quit", "exit"}:
                break
            if operator not in {"+", "-", "*", "/", "%"}:
                print("Choose +, -, *, or /. You can also choose %.")
                continue
            left = read_number("First number: ")
            right = read_number("Second number: ")
            try:
                result = calculate(left, operator, right)
                print(f"Result: {result:g}")
            except ValueError as error:
                print(error)
    except (EOFError, KeyboardInterrupt):
        print()
    print("Goodbye!")


if __name__ == "__main__":
    main()
