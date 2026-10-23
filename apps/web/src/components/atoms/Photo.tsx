import type { ImgHTMLAttributes } from 'react'

type Props = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'srcSet'> & {
  /** The photo's base path, e.g. /images/crete-coast: public/images has it as -800.webp and -1600.webp. */
  src: string
  /** How wide the photo shows, so the browser picks the smaller file on phones. Default: full width. */
  sizes?: string
}

/** A photo from public/images, in WebP at two widths. */
export function Photo({ src, sizes = '100vw', alt, ...props }: Props) {
  return (
    <img
      src={`${src}-1600.webp`}
      srcSet={`${src}-800.webp 800w, ${src}-1600.webp 1600w`}
      sizes={sizes}
      alt={alt}
      {...props}
    />
  )
}
