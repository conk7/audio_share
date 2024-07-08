// #[path = "../libs/lib.rs"]
// mod lib;

use rodio::{source::Source, Decoder, OutputStream};
use std::fs::File;
use std::io;
use std::io::BufReader;
use std::net::UdpSocket;
use std::thread;
use std::sync::{Arc, Mutex};


fn play_audio() {
    let (_stream, stream_handle) = OutputStream::try_default().unwrap();
    let file = BufReader::new(File::open("audio.mp3").unwrap());
    let source = Decoder::new(file).unwrap();
    stream_handle.play_raw(source.convert_samples()).unwrap();
    std::thread::sleep(std::time::Duration::from_secs(1));
}

fn read_chat(socket: Arc<Mutex<UdpSocket>>) {
    loop {
        let mut data = [0; 1024];
        let (len, src) = socket.lock().unwrap().recv_from(&mut data).unwrap();
        println!("\r{}:<{}", src, String::from_utf8_lossy(&data[..len]));
    }
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    let ip = match public_ip::addr().await {
        Some(ip) => {
            println!("My IP address {}", ip);
            ip
        }
        None => {
            println!("couldn't get an IP address");
            return Ok(());
        }
    };

    let mut src = String::new();
    io::stdin()
        .read_line(&mut src)
        .expect("IP should look like AddrV4:Port");

    let socket: Arc<Mutex<UdpSocket>> = Arc::new(Mutex::new(UdpSocket::bind(&src).expect("couldn't bind to address")));

    // let mut data = [0; 1024];
    // let (len, src) = socket.lock().unwrap().recv_from(&mut data).unwrap();
    let socket_clone = Arc::clone(&socket);
    thread::spawn(move || {
        read_chat(socket_clone)
    });

    loop {
        let mut input = String::new();
        io::stdin()
            .read_line(&mut input)
            .expect("Failed to read line");
        socket.lock().unwrap().send_to(input.as_bytes(), &src)?;
    }

    // Ok(())
}
