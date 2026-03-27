import os
from moviepy import VideoFileClip

def process_shot(input_video, start_time, end_time, output_name, output_dir, target_size_mb, mp4_res, gif_res):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    mp4_path = os.path.join(output_dir, f"{output_name}.mp4")
    gif_path = os.path.join(output_dir, f"{output_name}.gif")

    with VideoFileClip(input_video) as video:
        clip = video.subclipped(start_time, end_time)
        
        # --- Handle MP4 Export ---
        mp4_clip = clip
        if mp4_res != "Original":
            mp4_target_height = int(mp4_res.replace('p', ''))
            # Only downscale, don't upscale
            if clip.size[1] > mp4_target_height:
                mp4_clip = clip.resized(height=mp4_target_height)

        print(f"\n--- Exporting MP4: {mp4_path} ({mp4_res}) ---")
        mp4_clip.write_videofile(mp4_path, codec="libx264", audio_codec="aac", logger=None)

        # --- Handle GIF Export ---
        gif_clip = clip
        print(f"\n--- Exporting GIF: {gif_path} ---")
        print(f"Target size: {target_size_mb}MB | Requested Height: {gif_res}")
        
        if gif_res != "Original":
            gif_target_height = int(gif_res.replace('p', ''))
            if clip.size[1] > gif_target_height:
                gif_clip = clip.resized(height=gif_target_height)

        fps = 15
        scale = 1.0
        attempt = 1
        
        while True:
            print(f"Attempt {attempt}: Scale={scale:.2f}, FPS={fps}")
            temp_clip = gif_clip.resized(scale)
            
            # Using logger=None to keep terminal output clean during the loop
            temp_clip.write_gif(gif_path, fps=fps, logger=None)
            
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