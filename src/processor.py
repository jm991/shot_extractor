import os
from moviepy import VideoFileClip # <-- Updated import for v2.0

def process_shot(input_video, start_time, end_time, output_name, output_dir, target_size_mb, target_res):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    mp4_path = os.path.join(output_dir, f"{output_name}.mp4")
    gif_path = os.path.join(output_dir, f"{output_name}.gif")

    with VideoFileClip(input_video) as video:
        # <-- Updated method: subclip() is now subclipped()
        clip = video.subclipped(start_time, end_time)
        
        print(f"\n--- Exporting MP4: {mp4_path} ---")
        clip.write_videofile(mp4_path, codec="libx264", audio_codec="aac", logger=None)

        print(f"\n--- Exporting GIF: {gif_path} ---")
        print(f"Target size: {target_size_mb}MB | Requested Height: {target_res}")
        
        # Initial resize based on user selection
        if target_res != "Original":
            target_height = int(target_res.replace('p', ''))
            # Only downscale, don't upscale
            if clip.size[1] > target_height:
                # <-- Updated method: resize() is now resized()
                clip = clip.resized(height=target_height)

        fps = 15
        scale = 1.0
        attempt = 1
        
        while True:
            print(f"Attempt {attempt}: Scale={scale:.2f}, FPS={fps}")
            # <-- Updated method: resize() is now resized()
            temp_clip = clip.resized(scale)
            
            # Using logger=None to keep terminal output clean during the loop
            temp_clip.write_gif(gif_path, fps=fps, program='ffmpeg', logger=None)
            
            size_mb = os.path.getsize(gif_path) / (1024 * 1024)
            print(f"Resulting size: {size_mb:.2f} MB")
            
            if size_mb <= target_size_mb:
                print("Target size reached!\n")
                break
                
            # If it's too big, shrink it and try again
            if scale > 0.6:
                scale -= 0.15  # Reduce resolution by 15%
            elif fps > 8:
                fps -= 2       # Reduce framerate
            else:
                scale -= 0.1   # Keep shrinking as a last resort
                
            if scale <= 0.2:
                print("Reached minimum quality limits. Stopping compression.\n")
                break
                
            attempt += 1