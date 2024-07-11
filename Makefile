all: windows linux

windows:
	cargo build --release --target=x86_64-pc-windows-gnu

linux:
	cargo build --release --target=x86_64-unknown-linux-gnu

