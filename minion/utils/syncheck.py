"""This file checks two things:
1. Is the LLMs codegen completed for each benchmark?
2. Warn the code that are not compilable (it could be some impl issues).
"""

import ast
import threading
import traceback

import astunparse


def syntax_check(code, verbose=False) -> None:
    try:
        ast.parse(code)
        return True
    except (SyntaxError, MemoryError):
        if verbose:
            traceback.print_exc()
        return False

class TimeoutError(Exception):
    pass

def run_with_timeout(func, args, timeout=None) -> None:
    result = []
    def target() -> None:
        try:
            result.append(func(*args))
        except Exception as e:
            result.append(e)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError("Function execution timed out")
    if isinstance(result[0], Exception):
        raise result[0]
    return result[0]

def get_call_str(assert_statement: str) -> str:
    ast_parsed = ast.parse(assert_statement)
    try:
        call_str = ast_parsed.body[0].test.left # type: ignore
    except:
        call_str = ast_parsed.body[0].test # type: ignore

    return astunparse.unparse(call_str).strip()

def get_output(func: str, assert_statement: str, timeout: int = 2) -> str:
    try:
        exec(f"from typing import *\n{func}", globals())
        func_call = get_call_str(assert_statement)
        output = run_with_timeout(eval, (func_call, globals()), timeout)
        return output
    except TimeoutError:
        return "TIMEOUT"
    except Exception as e:
        return str(e)

def script(
    samples: str, dataset: str, nsample_check: int = None, verbose: bool = False
):
    # List[Dict{"task_id", "solution"}]
    solutions = load_solutions(samples)

    if dataset == "humaneval":
        from evalplus.data import get_human_eval_plus

        dataset = get_human_eval_plus()
        dataset_name = "HumanEval"
    elif dataset == "mbpp":
        from evalplus.data import get_mbpp_plus

        dataset = get_mbpp_plus()
        dataset_name = "Mbpp"

    logging.info(colored(f"Dataset: {dataset_name}", "blue"))

    id2solutions = {}
    for solution in solutions:
        task_id = solution["task_id"]
        if task_id not in id2solutions:
            id2solutions[task_id] = []
        if "solution" not in solution:
            assert "completion" in solution, "solution or completion must exist!"
            solution["solution"] = dataset[task_id]["prompt"] + solution["completion"]
        id2solutions[task_id].append(solution)

    logging.info(colored("==============================", "blue"))
    logging.info(colored(" ::: Checking completeness... ", "blue"))
    logging.info(colored(" ::::: All tasks complete?    ", "blue"))
    ndone = 0

    task_ids = dataset.keys()
    ntask = len(task_ids)
    for task_id in task_ids:
        if task_id not in id2solutions:
            logging.info(colored(f" ⚠️ {task_id} is missing!", "red"))
            continue
        nfiles = len(id2solutions[task_id])

        if nsample_check is None or nfiles <= nsample_check:
            ndone += 1
            continue

        logging.info(
            colored(
                f" ⚠️ {task_id} only has {nfiles} samples! But {nsample_check} are expected.",
                "red",
            )
        )

    # check if there is enough number of samples here.
    if nsample_check is not None:
        if ntask != ndone:
            ntbd = ntask - ndone
            logging.info(colored(f" ::::: ⚠️ {ntbd}/{ntask} tasks incomplete!", "red"))
        else:
            logging.info(colored(f" ::::: All {ntask} tasks complete!", "green"))

    logging.info(colored("==============================", "blue"))
    logging.info(colored(" ::: Checking compilation...  ", "blue"))
    logging.info(colored(" ::::: All code compilable?   ", "blue"))
    ncode = 0
    nwrong = 0
    for task_id in task_ids:
        # task_id must exist
        if task_id not in id2solutions:
            continue

        for solution in id2solutions[task_id]:
            ncode += 1
            code = solution["solution"]
            dbg_identifier = solution["_identifier"]
            if code.strip() == "":
                logging.info(colored(f" ⚠️ {dbg_identifier} is empty!", "red"))
                nwrong += 1
            elif not syntax_check(code, verbose):
                logging.info(colored(f" ⚠️ {dbg_identifier} is not compilable!", "red"))
                nwrong += 1
    if 0 != nwrong:
        logging.info(colored(f" ::::: ⚠️ {nwrong}/{ncode} code are not compilable!", "red"))
    else:
        logging.info(colored(f" ::::: All {ncode} code are compilable!", "green"))


def main() -> None:
    from fire import Fire

    Fire(script)


if __name__ == "__main__":
    main()
