## freeact.preproc.preprocess_prompt

```
preprocess_prompt(
    text: str, max_image_size: int = 1024
) -> str | Sequence[UserContent]
```

Main preprocessing entry point. Transforms prompt text into agent-ready content.

Currently delegates to preprocess_attachment_tags to resolve image attachments. Other tag types (e.g. `<skill>`) pass through unchanged for the agent to handle.

Parameters:

| Name             | Type  | Description                                                        | Default    |
| ---------------- | ----- | ------------------------------------------------------------------ | ---------- |
| `text`           | `str` | Prompt text, potentially containing <attachment> and <skill> tags. | *required* |
| `max_image_size` | `int` | Maximum dimension for images (downscaled if larger).               | `1024`     |

Returns:

| Type  | Description             |
| ----- | ----------------------- |
| \`str | Sequence[UserContent]\` |

## freeact.preproc.preprocess_attachment_tags

```
preprocess_attachment_tags(
    text: str, max_image_size: int = 1024
) -> str | Sequence[UserContent]
```

Resolve `<attachment path="..."/>` tags to multimodal content.

Scans `text` for attachment tags, collects image files from the referenced paths (a path may point to a single file or a directory), and loads each image as binary content. The original text is preserved as the last element of the returned list.

When no attachment tags are found, or none of the referenced paths contain images, the original text is returned unchanged as a plain string.

Parameters:

| Name             | Type  | Description                                                                                      | Default    |
| ---------------- | ----- | ------------------------------------------------------------------------------------------------ | ---------- |
| `text`           | `str` | Prompt text potentially containing <attachment path="..."/> tags.                                | *required* |
| `max_image_size` | `int` | Maximum dimension in pixels. Images exceeding this are downscaled while preserving aspect ratio. | `1024`     |

Returns:

| Type  | Description             |
| ----- | ----------------------- |
| \`str | Sequence[UserContent]\` |

Note

Directory paths include all images in that directory (non-recursive).
