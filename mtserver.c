#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <arpa/inet.h>
#include <sys/wait.h>
#include <signal.h>
#include <time.h>
#include <pthread.h>

#define BACKLOG 10 // how many pending connections queue will hold
#define MAXDATASIZE 100 // max size (bytes) of msgs

#define REQ_CTRLC -2
#define REQ_INVALID -1
#define REQ_INCOMPLETE 0
#define REQ_UPTIME 1
#define REQ_LOAD 2
#define REQ_EXIT 3

#define MAX_CONSEC_INV_REQ 3 // Number of consecutive invalid requests leading
                             // to automatic shutdown.

void startServThread(int fd);
int parseRequest(char *buf);
void *setupThread(void *fd);
int getThreadStatus(int i);
void setThreadStatus(int i, int status);
int currentLoad(void);
int sendall(int s, char *buf, int *len);

int MAX_THREADS;
struct thread_data *threadDataArray;
pthread_mutex_t mThreadData; // for modifying threadDataArray

struct thread_data {
    int t_status;
    int t_id;
    int t_fd; // File descriptor for thread's socket.
};

void sigchld_handler(int s) {
    while(waitpid(-1, NULL, WNOHANG) > 0);
}

// get sockaddr, IPv4 or IPv6:
void *get_in_addr(struct sockaddr *sa) {
    if (sa->sa_family == AF_INET) {
        return &(((struct sockaddr_in*)sa)->sin_addr);
    }
    
    return &(((struct sockaddr_in6*)sa)->sin6_addr);
}

int main(int argc, char **argv) {
    
    if (argc != 3) {
        printf("usage: 'mtserver max_threads port'\n");
        return 1;
    }
    
    MAX_THREADS = atoi(argv[1]);
    if (MAX_THREADS <= 0) {
        printf("Invalid max thread count: %d\n", MAX_THREADS);
        return 1;
    }
    
    char *PORT = argv[2];
    if (atoi(PORT) < 1024) {
        printf("Invalid port number: %d\n", atoi(PORT));
        return 1;
    }
    
    int sockfd, new_fd; // listen on sock_fd, new connection on new_fd
    struct addrinfo hints, *servinfo, *p;
    struct sockaddr_storage their_addr; // connector's address information
    socklen_t sin_size;
    struct sigaction sa;
    int yes = 1;
    char s[INET6_ADDRSTRLEN];
    int rv; // return value
    
    memset(&hints, 0, sizeof hints);
    hints.ai_family = AF_UNSPEC; // either IPv4 or IPv6
    hints.ai_socktype = SOCK_STREAM; // TCP
    hints.ai_flags = AI_PASSIVE; // use my IP
    
    if ((rv = getaddrinfo(NULL, PORT, &hints, &servinfo)) != 0) {
        fprintf(stderr, "getaddrinfo: %s\n", gai_strerror(rv));
        return 1;
    }
    
    // loop through all the results and bind to the first we can
    for(p = servinfo; p != NULL; p = p->ai_next) {
        if ((sockfd = socket(p->ai_family, p->ai_socktype, p->ai_protocol)) == -1) {
            perror("server: socket");
            continue;
        }
        
        if (setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(int)) == -1) {
            perror("setsockopt");
            exit(1);
        }
        
        if (bind(sockfd, p->ai_addr, p->ai_addrlen) == -1) {
            close(sockfd);
            perror("server: bind");
            continue;
        }
        
        break;
    }
    if (p == NULL) {
        fprintf(stderr, "server: failed to bind\n");
        return 2;
    }
    
    freeaddrinfo(servinfo); // all done with this structure
    
    if (listen(sockfd, BACKLOG) == -1) {
        perror("listen");
        exit(1);
    }
    
    sa.sa_handler = sigchld_handler; // reap all dead processes
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;
    if (sigaction(SIGCHLD, &sa, NULL) == -1) {
        perror("sigaction");
        exit(1);
    }
    
    printf("server: waiting for connections...\n");
    
    
    pthread_t *threads = malloc(MAX_THREADS * sizeof(pthread_t));
    threadDataArray = malloc(MAX_THREADS * sizeof(struct thread_data));
    memset(threadDataArray, 0, MAX_THREADS*sizeof(struct thread_data));
    pthread_mutex_init(&mThreadData, NULL);
    
    while(1) { // main accept() loop
        sin_size = sizeof their_addr;
        new_fd = accept(sockfd, (struct sockaddr *)&their_addr, &sin_size);
        if (new_fd == -1) {
            perror("accept");
            continue;
        }
        
        inet_ntop(their_addr.ss_family, 
                  get_in_addr((struct sockaddr *)&their_addr), s, sizeof s);
        //printf("server: got connection from %s\n", s);
        
        // Try to find an unused thread for the new connection...
        int tIndex = -1;
        int i;
        for(i = 0; i < MAX_THREADS; i++) {
            if (!getThreadStatus(i)) {
                setThreadStatus(i, 1);
                tIndex = i;
                break;
            }
        }
        if (tIndex < 0) {
            printf("No threads available...\n");
            close(new_fd);
            continue;
        }
        
        threadDataArray[tIndex].t_id = tIndex;
        threadDataArray[tIndex].t_fd = new_fd;
        
        int rc = pthread_create((pthread_t *) &threads[tIndex], NULL, setupThread, 
                                (void *) &threadDataArray[tIndex]);
        if (rc) {
            printf("ERROR; return code from pthread_create() is %d\n", rc);
            exit(-1);
        }
    }
    
    pthread_exit(NULL);
    return 0;
}

void *setupThread(void *threadData) {
    /* Wrapper that cleans up after the thread finishes. */
    struct thread_data *data;
    data = (struct thread_data *) threadData;
    
    startServThread((int) data->t_fd); // Run the thread.
    
    // Free up the thread.
    setThreadStatus(data->t_id, 0); 
    close((int) data->t_fd); 
    data->t_fd = -1;
}

void startServThread(int fd) {
    /* Main thread functionality: loop through recv() responding to client. */
    
    int numbytes;
    char buf[MAXDATASIZE];
    char *pos = buf;
    
    int consecInvReq = 0;
    
    while ((numbytes = recv(fd, pos, MAXDATASIZE-1, 0)) != -1) {
        if (numbytes == 0) { // Remote host disconnected -> we're done here.
            return;
        }
        
        pos += numbytes;
        *pos = '\0';
        
        int req;
        
        int RESPONSE_EXIT = 0;
        int RESPONSE_INV = -1;
        time_t seconds;
        int total;
        int i;
        
        while (req = parseRequest(buf)) {
            switch (req) {
                case REQ_UPTIME:
                    //printf("Responding to UPTIME request.\n");
                    seconds = time(NULL);
                    if (send(fd, &seconds, sizeof(int), 0) == -1)
                        perror("send");
                    consecInvReq = 0;
                    break;
                case REQ_LOAD:
                    //printf("Responding to LOAD request.\n");
                    total = currentLoad();
                    
                    if (send(fd, &total, sizeof(int), 0) == -1)
                        perror("send");
                    consecInvReq = 0;
                    break;
                case REQ_EXIT:
                    //printf("Responding to EXIT request.\n");
                    if (send(fd, &RESPONSE_EXIT, sizeof(int), 0) == -1)
                        perror("send");
                    return;
                case REQ_INVALID:
                    //printf("Responding to INVALID request.\n");
                    if (send(fd, &RESPONSE_INV, sizeof(int), 0) == -1)
                        perror("send");
                    consecInvReq++;
                    if (consecInvReq >= MAX_CONSEC_INV_REQ) {
                        return;
                    }
                    break;
                case REQ_CTRLC:
                    // No need to send response, just shut down.
                    return;
                default:
                    printf("Unknown request type...\n");
                    exit(0);
            }
        }
        
        pos = &buf[strlen(buf)]; // Always want pos to point to end of buf 
    }
}

int parseRequest(char *buf) {
    /* Return the request type. Reads buf chars to identify the request type. */
    
    char rUptime[] = "uptime";
    char rLoad[] = "load";
    char rExit[] = "exit";
    
    int isValidUptimeReq = 1;
    int isValidLoadReq = 1;
    int isValidExitReq = 1;
    
    char tbuf[MAXDATASIZE + 1]; // add one so we can always append our '\0'
    
    int i = 0;
    // Go one char at a time. Whenever a decision is made about some substring,
    // adjust the buffer by shifting over the entries, and return.
    while (i < strlen(buf)) { 
        
        if (buf[i] == 0x03) { // Ctrl+C
            //printf("CTRL+C DETECTED\n");
            memmove(buf, &buf[i + 1], strlen(buf));
            return REQ_CTRLC;
        }
        
        // Fill up our temp buffer as we go, used to analyze sub-string seen so far.
        tbuf[i] = buf[i];
        tbuf[i+1] = '\0';
        
        // First check if we have a complete valid request.
        if (strstr(tbuf, rUptime)) {
            //printf("uptime request detected\n");
            memmove(buf, &buf[i + 1], strlen(buf));
            return REQ_UPTIME;
        }
        else if (strstr(tbuf, rLoad)) {
            //printf("load request detected\n");
            memmove(buf, &buf[i + 1], strlen(buf));
            return REQ_LOAD;
        }
        else if (strstr(tbuf, rExit)) {
            //printf("load request detected\n");
            memmove(buf, &buf[i + 1], strlen(buf));
            return REQ_EXIT;
        }
        
        // If not, check that it's at least the start of a valid request.
        if (isValidUptimeReq) {
            if (strncmp(tbuf, rUptime, i+1)) {
                isValidUptimeReq = 0;
            }
        }
        if (isValidLoadReq) {
            if (strncmp(tbuf, rLoad, i+1)) {
                isValidLoadReq = 0;
            }
        }
        if (isValidExitReq) {
            if (strncmp(tbuf, rExit, i+1)) {
                isValidExitReq = 0;
            }
        }
        
        // If the substring can't ever become a valid request, invalidate it.
        if (!isValidUptimeReq && !isValidLoadReq && !isValidExitReq) {
            //printf("Invalid Request: %s\n", tbuf);
            memmove(buf, &buf[i + 1], strlen(buf));
            return -1;
        }
        
        i++;
    }
    
    // If we've gotten this far, it's an incomplete (but valid so far) request.
    //printf("Incomplete request: '%s'\n", buf);
    return 0;
}

int getThreadStatus(int i) {
    int status;
    
    pthread_mutex_lock(&mThreadData);
    status = threadDataArray[i].t_status;
    pthread_mutex_unlock(&mThreadData);
    
    return status;
}

void setThreadStatus(int i, int status) {
    pthread_mutex_lock(&mThreadData);
    threadDataArray[i].t_status = status;
    pthread_mutex_unlock(&mThreadData);
}

int currentLoad(void) {
    /* Return number of threads currently connected. */
    int load = 0;
    int i;
    pthread_mutex_lock(&mThreadData);
    for (i = 0; i < MAX_THREADS; i++) {
        if (threadDataArray[i].t_status) {
            load++;
        }
    }
    pthread_mutex_unlock(&mThreadData);
    return load;
}

/* from beej */
int sendall(int s, char *buf, int *len) {
    int total = 0; // how many bytes we've sent
    int bytesleft = *len; //how many we have left to send
    int n;
    
    while (total < *len) {
        n = send(s, buf+total, bytesleft, 0);
        if (n == -1)
            break;
        total += n;
        bytesleft -= n;
    }
    
    *len = total; // number of bytes actually sent
    
    return (n == 1 ? -1 : 0);
}
