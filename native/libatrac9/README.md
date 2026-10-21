# LibAtrac9

ATRAC9 decoder by Alex Barney (MIT, see `LICENSE`), from https://github.com/Thealexbarney/LibAtrac9 (C version, as vendored by KytyPS5 / shadPS4).
AnyPS5 Console uses it to play the `sce_sys/snd0.at9` theme of each game. Built as `atrac9.dll` (Windows) or `libatrac9.so` (Linux):

```
x86_64-w64-mingw32-gcc -O2 -shared -static-libgcc -o atrac9.dll src/*.c -Wl,--out-implib,NUL -lm
gcc -O2 -shared -fPIC -o libatrac9.so src/*.c -lm
```
