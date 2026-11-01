Explain the code I point you at so I could modify it safely, not just read it.

Give me, in this order:
1. **In one line**: what this does and who calls it.
2. **The shape**: inputs, outputs, side effects (files, network, globals, state
   it mutates). Note anything that isn't obvious from the signature.
3. **The walk-through**: the main path step by step, then the branches and error
   paths. Use the real names from the code.
4. **The sharp edges**: assumptions it makes, inputs that would break it,
   anything surprising or load-bearing that a change could easily violate.
5. **If I wanted to change X**: where I'd touch, and what else depends on it.

Quote short snippets with line references instead of pasting the whole thing.
If something in the code looks wrong, say so, but keep it separate from the
explanation. If you're unsure what a part does, say "unclear" rather than
inventing a reason.
