#!/usr/bin/python3

from opcodes import *

def build_ir(code):
    blocks = build_basic_blocks(code)
    for block in blocks:
        build_ir_nodes(block)
    return blocks

class BasicBlock:
    def __init__(self, code=None):
        self.code = code
        if code:
            self.address = code[0].address
        else:
            self.address = None
        self.predecessors = []
        self.successors = []
        self.ir = []

    def add_successor(self, other):
        self.successors.append(other)
        other.predecessors.append(self)

def build_basic_blocks(code):
    boundaries = set()
    blocks = {}
    basic_blocks = []

    for i, instruction in enumerate(code):
        if EQ <= instruction.opcode <= GEF:
            boundaries.add(instruction.address)
            boundaries.add(instruction.operand-1)
        elif instruction.opcode == JUMP:
            boundaries.add(instruction.address)
            if instruction.operand is not None:
                boundaries.add(instruction.operand-1)
    boundaries.add(code[-1].address)

    block = BasicBlock()
    start = 0
    for i, instruction in enumerate(code):
        if instruction.address in boundaries:
            next_block = BasicBlock()
            if instruction is not code[-1]:
                block.add_successor(next_block)
            block.code = code[start:i+1]
            block.address = code[start].address
            blocks[block.address] = block
            basic_blocks.append(block)
            block = next_block
            start = i + 1

    for block in basic_blocks:
        last_instruction = block.code[-1]
        if EQ <= last_instruction.opcode <= GEF:
            block.add_successor(blocks[last_instruction.operand])
        elif last_instruction.opcode == JUMP:
            if last_instruction.operand is not None:
                block.add_successor(blocks[last_instruction.operand])

    return basic_blocks

class IRNode:
    def __init__(self, instruction, *children):
        self.instruction = instruction
        self.children = list(children)
        self.opcode = instruction.opcode
        self.value = instruction.operand

    @property
    def left(self):
        return self.children[0]

    @property
    def right(self):
        return self.children[1]

    @property
    def child(self):
        return self.children[0]

    def __repr__(self):
        return f'{self.__class__.__name__} {mnemonics.get(self.opcode, str(self.opcode))}'

    def __str__(self):
        return self.__repr__()

def build_ir_nodes(block):
    """Build a list of IR nodes from a basic block.

    This can't handle cases like this:

            ...
            EQ b
        a:
            CONST 1
            CONST c
            JUMP
        b:
            CONST 2
        c:
            (1 or 2?)

    Luckily, code generated by lcc seems to always have an empty opstack at
    basic block boundaries.
    """

    stack = []
    nodes = []

    for instruction in block.code:
        opcode = instruction.opcode

        if opcode == ENTER:
            nodes.append(IRNode(instruction))

        elif opcode in (PUSH, CONST, LOCAL):
            stack.append(IRNode(instruction))

        elif LOAD1 <= opcode <= LOAD4:
            stack.append(IRNode(instruction, stack.pop()))

        elif STORE1 <= opcode <= STORE4:
            tos, nis = stack.pop(), stack.pop()
            nodes.append(IRNode(instruction, nis, tos))

        elif opcode == BLOCK_COPY or opcode in comparison_ops:
            tos, nis = stack.pop(), stack.pop()
            nodes.append(IRNode(instruction, nis, tos))

        elif opcode in (JUMP, LEAVE):
            nodes.append(IRNode(instruction, stack.pop()))

        elif opcode == ARG:
            nodes.append(IRNode(instruction, stack.pop()))

        elif opcode == CALL:
            stack.append(IRNode(instruction, stack.pop()))

        elif opcode == POP:
            # If we're popping the result of a CALL, make it a statement.
            # Otherwise, ignore pops.
            tos = stack.pop()
            if tos.opcode == CALL:
                nodes.append(tos)

        elif opcode in unary_ops:
            stack.append(IRNode(instruction, stack.pop()))

        elif opcode in binary_ops:
            tos, nis = stack.pop(), stack.pop()
            stack.append(IRNode(instruction, nis, tos))

        else:
            raise Exception(f'unhandled opcode {mnemonics[opcode]}')

    block.ir = nodes
