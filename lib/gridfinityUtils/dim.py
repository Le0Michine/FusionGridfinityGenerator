from enum import Enum
import adsk.core

class DimKind(Enum):
    # Fusion gets the plain number, the expression is only kept for combining with other dims
    VALUE = 'value'
    # Fusion gets the expression, so the model follows the parameters it references
    EXPRESSION = 'expression'

class Dim:
    """A number for the generator's own math together with the Fusion expression it stands for.
    The kind decides which of the two is fed to Fusion, combining dims keeps the expression kind if any side has it.
    Values are in Fusion internal units, cm for lengths."""

    def __init__(self, value: float, expression: str, kind: DimKind = DimKind.VALUE, isCompound: bool = False):
        self.value = value
        self.expression = expression
        self.kind = kind
        # compound expressions get parentheses when used as an operand
        self.isCompound = isCompound

    @staticmethod
    def length(value: float) -> 'Dim':
        return Dim(value, f'{round(value * 10, 6):g} mm')

    @staticmethod
    def asLength(value) -> 'Dim':
        """Dims pass through, plain values become lengths"""
        return value if isinstance(value, Dim) else Dim.length(value)

    @staticmethod
    def number(value: float, expression: str = None) -> 'Dim':
        return Dim(value, expression if expression is not None else f'{value:g}')

    @staticmethod
    def parameter(parameter: adsk.core.Base) -> 'Dim':
        return Dim(parameter.value, parameter.name, DimKind.EXPRESSION)

    @property
    def isExpression(self) -> bool:
        return self.kind == DimKind.EXPRESSION

    def asExpression(self) -> 'Dim':
        """Same dim fed to Fusion as its expression, to keep the formula visible in the model"""
        return Dim(self.value, self.expression, DimKind.EXPRESSION, self.isCompound)

    def abs(self) -> 'Dim':
        return Dim(abs(self.value), f'abs({self.expression})', self.kind)

    @staticmethod
    def min(first: 'Dim', second: 'Dim') -> 'Dim':
        """The smaller of the two, as Fusion's min function, so it changes with the parameters"""
        return Dim._function('min', first, second, min(first.value, second.value))

    @staticmethod
    def max(first: 'Dim', second: 'Dim') -> 'Dim':
        """The larger of the two, as Fusion's max function, so it changes with the parameters"""
        return Dim._function('max', first, second, max(first.value, second.value))

    @staticmethod
    def _function(name: str, first: 'Dim', second: 'Dim', value: float) -> 'Dim':
        kind = DimKind.EXPRESSION if first.isExpression or second.isExpression else DimKind.VALUE
        # Fusion separates function arguments with semicolons
        return Dim(value, f'{name}({first.expression}; {second.expression})', kind)

    def _operand(self) -> str:
        return f'({self.expression})' if self.isCompound else self.expression

    @staticmethod
    def _coerce(other, operator: str) -> 'Dim':
        if isinstance(other, Dim):
            return other
        if operator in ('*', '/') and isinstance(other, (int, float)):
            return Dim.number(other)
        # a bare number has no unit, so sums need it spelled out as Dim.length or Dim.number
        raise TypeError(f"Dim {operator} {type(other).__name__} needs a Dim operand")

    @staticmethod
    def _combine(left: 'Dim', right: 'Dim', operator: str, value: float) -> 'Dim':
        kind = DimKind.EXPRESSION if left.isExpression or right.isExpression else DimKind.VALUE
        return Dim(value, f'{left._operand()} {operator} {right._operand()}', kind, True)

    def __add__(self, other):
        other = Dim._coerce(other, '+')
        return Dim._combine(self, other, '+', self.value + other.value)

    def __radd__(self, other):
        other = Dim._coerce(other, '+')
        return Dim._combine(other, self, '+', other.value + self.value)

    def __sub__(self, other):
        other = Dim._coerce(other, '-')
        return Dim._combine(self, other, '-', self.value - other.value)

    def __rsub__(self, other):
        other = Dim._coerce(other, '-')
        return Dim._combine(other, self, '-', other.value - self.value)

    def __mul__(self, other):
        other = Dim._coerce(other, '*')
        return Dim._combine(self, other, '*', self.value * other.value)

    def __rmul__(self, other):
        other = Dim._coerce(other, '*')
        return Dim._combine(other, self, '*', other.value * self.value)

    def __truediv__(self, other):
        other = Dim._coerce(other, '/')
        return Dim._combine(self, other, '/', self.value / other.value)

    def __rtruediv__(self, other):
        other = Dim._coerce(other, '/')
        return Dim._combine(other, self, '/', other.value / self.value)

    def __repr__(self):
        return f'Dim({self.value!r}, {self.expression!r}, {self.kind.name})'

def valueOf(value) -> float:
    """The number behind a dim or a plain value, for the generator's own math"""
    return value.value if isinstance(value, Dim) else value

def valueInput(value) -> adsk.core.ValueInput:
    """The only place a dim's kind is looked at, everything handed to Fusion goes through here or applyTo"""
    if isinstance(value, Dim):
        if value.isExpression:
            return adsk.core.ValueInput.createByString(value.expression)
        return adsk.core.ValueInput.createByReal(value.value)
    return adsk.core.ValueInput.createByReal(value)

def applyTo(parameter: adsk.core.Base, value):
    """Drives an existing model parameter, e.g. a sketch dimension, plain values are left as created"""
    if isinstance(value, Dim) and value.isExpression:
        parameter.expression = value.expression
