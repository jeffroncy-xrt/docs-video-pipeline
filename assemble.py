import os,build
from beats import BEATS
clips=[f"render/clip_{i:02d}.mp4" for i in range(len(BEATS))]
assert all(os.path.exists(c) for c in clips), "missing clips"
open("render/list.txt","w").write("\n".join(f"file '{os.path.abspath(c)}'" for c in clips))
build.run(["ffmpeg","-y","-f","concat","-safe","0","-i","render/list.txt","-c","copy","render/joined.mp4"])
total=build.dur_of("render/joined.mp4")
print(f"joined = {total:.1f}s ({total/60:.2f} min)")
build.drone(total,"render/drone.wav")
print("drone ok", build.dur_of("render/drone.wav"))
