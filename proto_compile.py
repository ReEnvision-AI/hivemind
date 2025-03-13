import glob
import re

def proto_compile(output_path):
    import grpc_tools.protoc

    cli_args = [
        "grpc_tools.protoc",
        "--proto_path=hivemind/proto",
        f"--python_out={output_path}",
    ] + glob.glob("hivemind/proto/*.proto")
    print(f"{cli_args=}")
    code = grpc_tools.protoc.main(cli_args)
    if code:  # hint: if you get this error in jupyter, run in console for richer error message
        raise ValueError(f"{' '.join(cli_args)} finished with exit code {code}")
    # Make pb2 imports in generated scripts relative
    for script in glob.iglob(f"{output_path}/*.py"):
        with open(script, "r+") as file:
            code = file.read()
            file.seek(0)
            file.write(re.sub(r"\n(import .+_pb2.*)", "from . \\1", code))
            file.truncate()

if __name__ == "__main__":
    proto_compile("hivemind/proto")