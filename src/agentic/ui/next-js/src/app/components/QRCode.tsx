import React from 'react';
import Image from 'next/image';

interface QRCodeProps {
  src: string;
  alt: string;
  width?: number;
  height?: number;
}

const QRCode: React.FC<QRCodeProps> = ({
  src,
  alt,
  width = 100,
  height = 40
}) => {
  return (
    <div className="fixed bottom-4 left-4 z-50">
      <div className="bg-background/70 backdrop-blur-sm p-2 rounded-lg shadow-md">
        <Image
          src={src}
          alt={alt}
          width={width}
          height={height}
          priority
        />
      </div>
    </div>
  );
};

export default QRCode;