import math


def calculate(left: float, operator: str, right: float) -> float:
    """Calculate one operation, rejecting invalid operators and zero divisors."""
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        if right == 0:
            raise ValueError("Cannot divide by zero.")
        return left / right
    raise ValueError("Choose +, -, *, or /.")


def read_number(prompt: str, answer: float | None = None) -> float:
    """Read a finite number or ans, allowing the user to retry invalid input."""
    while True:
        text = input(prompt).strip()
        if text.lower() == "ans":
            if answer is not None:
                return answer
            print("No previous result yet.")
            continue
        try:
            number = float(text)
            if math.isfinite(number):
                return number
        except ValueError:
            pass
        print("Please enter a finite number.")


def main() -> None:
    print("Calculator: +, -, *, / (enter q to quit)")
    answer = None
    try:
        while True:
            operator = input("Operation: ").strip().lower()
            if operator in {"q", "quit", "exit"}:
                break
            if operator not in {"+", "-", "*", "/"}:
                print("Choose +, -, *, or /.")
                continue
            left = read_number("First number: ", answer)
            right = read_number("Second number: ", answer)
            try:
                result = calculate(left, operator, right)
                answer = result
                print(f"Result: {result:g}")
            except ValueError as error:
                print(error)
    except (EOFError, KeyboardInterrupt):
        print()
    print("Goodbye!")


if __name__ == "__main__":
    main()
